"""Authenticated prototype API. No real posting or legacy campaign execution."""
import asyncio
from contextlib import asynccontextmanager, suppress
import hmac
from pathlib import Path
import time
from uuid import UUID
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from . import devices, jobs
from .legacy_preview import preview_legacy_plan
from .models import AgentEvent, Diagnostic, Empty, Enrollment, Heartbeat, Renewal
from .store import DomainError, Store


def create_app(db_path: Path, owner_token: str, *, legacy_config: Path | None = None, clock=time.time):
    if len(owner_token) < 32:
        raise ValueError('OWNER_CREDENTIAL_REQUIRED')
    store = Store(db_path, clock)
    heartbeat_state = {'last_tick': None, 'healthy': False}

    async def recover_loop():
        while True:
            try:
                with store.transaction() as db:
                    store.recover(db)
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

    app = FastAPI(title='StoryFX — socle de diagnostic', version='0.1.0',
                  docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store = store
    bearer = HTTPBearer(auto_error=False)

    def credential(value: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if value is None or value.scheme.lower() != 'bearer':
            raise DomainError('UNAUTHORIZED', 401)
        return value.credentials

    def owner(token: str = Depends(credential)):
        if not hmac.compare_digest(token.encode('utf-8'), owner_token.encode('utf-8')):
            raise DomainError('UNAUTHORIZED', 401)
        return 'validation_owner'

    def agent(token: str = Depends(credential)):
        return store.device(token)

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
                             'recovery_worker_ok': bool(recent_tick and heartbeat_state['healthy'])},
                            status_code=200 if healthy else 503)

    @app.get('/v1/dashboard', dependencies=[Depends(owner)])
    def dashboard():
        return store.dashboard()

    @app.post('/v1/pairings', dependencies=[Depends(owner)])
    def pairing(_body: Empty):
        store.throttle('pairings_created', maximum=20, period=60)
        return devices.create_pairing(store)

    @app.post('/v1/devices/enroll')
    def enrollment(body: Enrollment):
        store.throttle('enrollment_attempts', maximum=30, period=60)
        return devices.enroll(store, body)

    @app.post('/v1/devices/heartbeat')
    def contact(body: Heartbeat, device_id=Depends(agent)):
        return devices.heartbeat(store, device_id, body)

    @app.post('/v1/devices/{device_id}/revoke', dependencies=[Depends(owner)])
    def revoke(device_id: UUID, _body: Empty):
        return devices.revoke(store, str(device_id))

    @app.post('/v1/diagnostics', dependencies=[Depends(owner)])
    def diagnostic(body: Diagnostic):
        return jobs.enqueue(store, body)

    @app.post('/v1/jobs/{job_id}/cancel', dependencies=[Depends(owner)])
    def cancel_job(job_id: UUID, _body: Empty):
        return jobs.cancel(store, str(job_id))

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
        app.mount('/dashboard', StaticFiles(directory=dashboard_root, html=True), name='dashboard')
    return app
