"""Authenticated prototype API. No real posting or legacy campaign execution."""
import asyncio
from contextlib import asynccontextmanager, suppress
import hmac
from pathlib import Path
import time
from uuid import UUID
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from . import devices, jobs
from .legacy_preview import preview_legacy_plan
from .models import AgentEvent, Diagnostic, Empty, Enrollment, Heartbeat, Renewal
from .store import DomainError, Store


def create_app(db_path: Path, owner_token: str | None, *, legacy_config: Path | None = None,
               clock=time.time, auth_client=None, encryption_key=None, origin='https://story.formafx.com'):
    if auth_client is None and (owner_token is None or len(owner_token) < 32):
        raise ValueError('OWNER_CREDENTIAL_REQUIRED')
    store = Store(db_path, clock)
    sessions = None
    if auth_client is not None:
        from .auth_sessions import AuthSessions
        sessions = AuthSessions(store, auth_client, encryption_key)
    heartbeat_state = {'last_tick': None, 'healthy': False}

    async def recover_loop():
        while True:
            try:
                with store.transaction() as db:
                    store.recover(db)
                await asyncio.to_thread(app.state.control_scheduler.tick)
                heartbeat_state.update(last_tick=clock(), healthy=True)
            except Exception:
                heartbeat_state['healthy'] = False
            await asyncio.sleep(10)

    @asynccontextmanager
    async def lifespan(_app):
        task = asyncio.create_task(recover_loop())
        await asyncio.sleep(0)
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title='StoryFX — pilote privé', version='0.2.0',
                  docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store = store
    bearer = HTTPBearer(auto_error=False)

    def credential(value: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if value is None or value.scheme.lower() != 'bearer':
            raise DomainError('UNAUTHORIZED', 401)
        return value.credentials

    def owner(request: Request, value: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if sessions is not None:
            from .auth_routes import COOKIE
            if request.method not in ('GET', 'HEAD') and request.headers.get('origin') != origin:
                raise DomainError('ORIGIN_REFUSED', 403)
            return sessions.require(request.cookies.get(COOKIE, ''))
        token = value.credentials if value and value.scheme.lower() == 'bearer' else ''
        if not hmac.compare_digest(token.encode('utf-8'), owner_token.encode('utf-8')):
            raise DomainError('UNAUTHORIZED', 401)
        return {'id': 'validation_owner', 'session_id': None}

    def agent(token: str = Depends(credential)):
        identity = store.device(token)
        if sessions is not None:
            if not identity.auth_session_hash:
                raise DomainError('UNAUTHORIZED', 401)
            user = sessions.require_hash(identity.auth_session_hash)
            if user['id'] != identity.owner_id:
                raise DomainError('UNAUTHORIZED', 401)
        return identity

    if sessions is not None:
        from .auth_routes import build_auth_router
        app.include_router(build_auth_router(sessions, origin))
        app.state.auth_sessions = sessions

    from .control_routes import build_control_router
    control_router, scheduler = build_control_router(store, sessions, owner, credential, agent)
    app.state.control_scheduler = scheduler
    app.include_router(control_router)

    @app.exception_handler(DomainError)
    async def domain_error(_request, error):
        return JSONResponse({'error': error.code}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _error):
        # The default Pydantic response can echo credentials or pairing input.
        return JSONResponse({'error': 'INVALID_REQUEST'}, status_code=422)

    @app.middleware('http')
    async def security_headers(request: Request, call_next):
        try:
            content_length = int(request.headers.get('content-length', '0') or '0')
        except ValueError:
            return JSONResponse({'error': 'INVALID_REQUEST'}, status_code=400)
        if content_length > 16384:
            return JSONResponse({'error': 'REQUEST_TOO_LARGE'}, status_code=413)
        if request.method in ('POST', 'PUT', 'PATCH'):
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 16384:
                    return JSONResponse({'error': 'REQUEST_TOO_LARGE'}, status_code=413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        return response

    @app.get('/health')
    def health():
        with store.transaction() as db:
            database_ok = db.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        recent_tick = heartbeat_state['last_tick'] is not None and clock() - heartbeat_state['last_tick'] <= 30
        healthy = database_ok and recent_tick and heartbeat_state['healthy']
        return JSONResponse({'status': 'ok' if healthy else 'degraded', 'mode': 'diagnostic_only',
                             'publishing_enabled': False, 'database_ok': database_ok,
                             'recovery_worker_ok': bool(recent_tick and heartbeat_state['healthy']),
                             'account_auth_enabled': sessions is not None, 'version': '0.3.0',
                             'control_center_mode': 'windows_bridge', 'windows_publication_enabled': True,
                             'android_publication_enabled': True, 'android_executor':'whatsapp_images_pilot', 'scheduler_available':True,
                             'manual_android_retry_available': True, 'publication_failure_stages': True,
                             'scheduler_worker_ok':bool(recent_tick and heartbeat_state['healthy']),
                             'scheduler_tick_seconds':10},
                            status_code=200 if healthy else 503)

    @app.get('/v1/dashboard')
    def dashboard(user=Depends(owner)):
        return store.dashboard(user['id'])

    @app.post('/v1/pairings')
    def pairing(_body: Empty, user=Depends(owner)):
        store.throttle('pairings_created', maximum=20, period=60)
        return devices.create_pairing(store, user['id'], user['session_id'])

    @app.post('/v1/devices/enroll')
    def enrollment(body: Enrollment):
        store.throttle('enrollment_attempts', maximum=30, period=60)
        return devices.enroll(store, body)

    @app.post('/v1/devices/heartbeat')
    def contact(body: Heartbeat, device_id=Depends(agent)):
        return devices.heartbeat(store, device_id, body)

    @app.post('/v1/devices/{device_id}/revoke')
    def revoke(device_id: UUID, _body: Empty, user=Depends(owner)):
        return devices.revoke(store, str(device_id), user['id'])

    @app.post('/v1/diagnostics')
    def diagnostic(body: Diagnostic, user=Depends(owner)):
        return jobs.enqueue(store, body, user['id'])

    @app.post('/v1/jobs/{job_id}/cancel')
    def cancel_job(job_id: UUID, _body: Empty, user=Depends(owner)):
        return jobs.cancel(store, str(job_id), user['id'])

    @app.post('/v1/agent/claim')
    def next_job(_body: Empty, device_id=Depends(agent)):
        return jobs.claim(store, device_id)

    @app.post('/v1/agent/jobs/{job_id}/events')
    def event(job_id: UUID, body: AgentEvent, device_id=Depends(agent)):
        return jobs.receive_event(store, device_id, str(job_id), body)

    @app.post('/v1/agent/jobs/{job_id}/renew')
    def renewal(job_id: UUID, body: Renewal, device_id=Depends(agent)):
        return jobs.renew(store, device_id, str(job_id), body.lease_token)

    @app.post('/v1/import-preview', dependencies=[Depends(owner)])
    def preview(_body: Empty):
        if legacy_config is None:
            raise DomainError('LEGACY_IMPORT_NOT_CONFIGURED', 503)
        try:
            return preview_legacy_plan(legacy_config)
        except ValueError:
            raise DomainError('LEGACY_IMPORT_INVALID', 503) from None

    @app.get('/')
    def root():
        return RedirectResponse('/dashboard/')

    dashboard_root = Path(__file__).resolve().parents[2] / 'dashboard'
    if dashboard_root.is_dir():
        @app.get('/agent/connect')
        def agent_connect():
            return FileResponse(dashboard_root / 'login' / 'index.html')

        app.mount('/login', StaticFiles(directory=dashboard_root / 'login', html=True), name='login')
        app.mount('/dashboard', StaticFiles(directory=dashboard_root, html=True), name='dashboard')
    return app
