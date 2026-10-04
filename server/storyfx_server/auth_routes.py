"""Private StoryFX browser authentication and native enrollment endpoints."""
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from .agent_auth import AgentAuth
from .auth_models import (AgentAuthorize, AgentExchange, AgentStart, Email,
                          OtpVerify, PasswordLogin, PasswordUpdate)
from .models import Empty
from .store import DomainError


COOKIE = '__Host-storyfx_session'
SSO_COOKIE = '__Host-storyfx_sso'


def build_auth_router(sessions, origin):
    router = APIRouter()
    mobile = AgentAuth(sessions.store, sessions, origin)
    callback = origin + '/auth/sso/callback'

    def browser_origin(request: Request):
        if request.headers.get('origin') != origin:
            raise DomainError('ORIGIN_REFUSED', 403)

    def principal(request: Request):
        return sessions.require(request.cookies.get(COOKIE, ''))

    def session_response(tokens, response, verified=False):
        cookie = sessions.create(tokens)
        if verified:
            sessions.password_verified(cookie)
        response.set_cookie(COOKIE, cookie, secure=True, httponly=True,
                            samesite='lax', max_age=sessions.max_age, path='/')
        return {'authenticated': True, 'user': {key: tokens[key] for key in ('id', 'email')},
                'access': 'formafx_active_owner'}

    @router.post('/v1/auth/login', dependencies=[Depends(browser_origin)])
    def login(body: PasswordLogin, response: Response):
        sessions.store.throttle('login:' + body.email, maximum=8, period=60)
        return session_response(sessions.client.password(body.email, body.password), response)

    @router.post('/v1/auth/otp/request', dependencies=[Depends(browser_origin)])
    def request_otp(body: Email):
        sessions.store.throttle('otp:' + body.email, maximum=1, period=60)
        sessions.client.request_otp(body.email)
        return {'requested': True, 'retry_after': 60}

    @router.post('/v1/auth/otp/verify', dependencies=[Depends(browser_origin)])
    def verify_otp(body: OtpVerify, response: Response):
        sessions.store.throttle('verify:' + body.email, maximum=8, period=60)
        return session_response(sessions.client.verify_otp(body.email, body.code), response, verified=True)

    @router.put('/v1/auth/password', dependencies=[Depends(browser_origin)])
    def update_password(body: PasswordUpdate, user=Depends(principal)):
        if body.password != body.confirmation:
            raise DomainError('PASSWORD_CONFIRMATION_MISMATCH', 400)
        sessions.consume_password_verification(user['session_id'])
        sessions.client.call('PUT', '/auth/v1/user', {'password': body.password}, user['tokens']['access_token'])
        return {'updated': True}

    @router.get('/v1/auth/session')
    def session(user=Depends(principal)):
        return {'authenticated': True, 'user': {key: user[key] for key in ('id', 'email')},
                'access': 'formafx_active_owner'}

    @router.post('/v1/auth/logout', dependencies=[Depends(browser_origin)])
    def logout(_body: Empty, request: Request, response: Response):
        sessions.delete(request.cookies.get(COOKIE, ''))
        response.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='lax')
        return {'authenticated': False}

    @router.post('/v1/auth/sso/start', dependencies=[Depends(browser_origin)])
    def sso_start(_body: Empty, response: Response):
        cookie, state = sessions.sso_start()
        response.set_cookie(SSO_COOKIE, cookie, secure=True, httponly=True, samesite='lax', max_age=600, path='/')
        return {'redirect_to': 'https://auth.formafx.com/sso/start?' + urlencode(
            {'app': 'storyfx', 'return_to': callback, 'state': state})}

    @router.get('/auth/sso/callback')
    def sso_callback(request: Request, code: str = '', state: str = ''):
        if not 32 <= len(code) <= 180 or not 24 <= len(state) <= 180:
            raise DomainError('SSO_CALLBACK_INVALID', 400)
        sessions.sso_consume(request.cookies.get(SSO_COOKIE, ''), state)
        payload = sessions.client.call('POST', '/functions/v1/formafx-sso-handoff/exchange',
                                      {'app': 'storyfx', 'return_to': callback, 'state': state, 'code': code},
                                      sessions.client.anon_key)
        if payload.get('ok') is not True:
            raise DomainError('SSO_EXCHANGE_REFUSED', 401)
        tokens = sessions.client.tokens(payload.get('session'))
        response = RedirectResponse('/login/?connected=1', status_code=303)
        session_response(tokens, response)
        response.delete_cookie(SSO_COOKIE, path='/', secure=True, httponly=True, samesite='lax')
        return response

    @router.post('/v1/auth/agent/start')
    def agent_start(body: AgentStart):
        sessions.store.throttle('agent_auth_start', maximum=30, period=60)
        return mobile.start(body)

    @router.post('/v1/auth/agent/authorize', dependencies=[Depends(browser_origin)])
    def agent_authorize(body: AgentAuthorize, user=Depends(principal)):
        return mobile.authorize(body.request_id, user)

    @router.get('/v1/auth/agent/request')
    def agent_request(request_id: str, _user=Depends(principal)):
        if len(request_id) != 43:
            raise DomainError('AGENT_REQUEST_INVALID', 400)
        return mobile.describe(request_id)

    @router.post('/v1/auth/agent/exchange')
    def agent_exchange(body: AgentExchange):
        sessions.store.throttle('agent_auth_exchange', maximum=30, period=60)
        return mobile.exchange(body)

    return router
