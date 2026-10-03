"""No provider email or social publication is triggered by these fixtures."""
import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse
from uuid import uuid4
from cryptography.fernet import Fernet
import pytest
from fastapi.testclient import TestClient
from storyfx_server.api import create_app
from storyfx_server.store import DomainError


ORIGIN = 'https://story.formafx.com'


class FakeAuth:
    anon_key = 'synthetic-public-key'

    def __init__(self, now):
        self.now, self.denied, self.refreshes = now, set(), 0

    def owner(self, access):
        subject = access.replace('access-', '').replace('-rotated', '')
        if subject in self.denied:
            raise DomainError('OWNER_ACCESS_REQUIRED', 403)
        return {'id': subject, 'email': subject + '@example.invalid'}

    def password(self, email, password):
        if password != 'synthetic-password':
            raise DomainError('AUTH_REFUSED', 401)
        subject = email.split('@')[0]
        return {**self.owner('access-' + subject), 'access_token': 'access-' + subject,
                'refresh_token': 'refresh-' + subject, 'expires_at': self.now[0] + 3600}

    def refresh(self, refresh):
        self.refreshes += 1
        subject = refresh.removeprefix('refresh-').removesuffix('-rotated')
        return {**self.owner('access-' + subject), 'access_token': 'access-' + subject + '-rotated',
                'refresh_token': 'refresh-' + subject + '-rotated', 'expires_at': self.now[0] + 3600}

    def verify_otp(self, email, code):
        if code != '123456':
            raise DomainError('AUTH_REFUSED', 401)
        return self.password(email, 'synthetic-password')

    def request_otp(self, email):
        return None

    def call(self, method, path, body, access=None):
        if path == '/auth/v1/user' and method == 'PUT':
            return {}
        if path == '/functions/v1/formafx-sso-handoff/exchange':
            return {'ok': True, 'session': self.password('owner-a@example.invalid', 'synthetic-password')}
        raise AssertionError('Unexpected synthetic provider call')

    def tokens(self, payload):
        return payload


@pytest.fixture
def private(tmp_path):
    now = [1700000000.0]
    provider = FakeAuth(now)
    app = create_app(tmp_path / 'private.db', None, auth_client=provider,
                     encryption_key=Fernet.generate_key(), clock=lambda: now[0])
    with TestClient(app, base_url=ORIGIN) as browser:
        yield app, browser, provider, now


def login(browser, subject='owner-a'):
    return browser.post('/v1/auth/login', headers={'Origin': ORIGIN},
                        json={'email': subject + '@example.invalid', 'password': 'synthetic-password'})


def enroll(browser):
    verifier = secrets.token_urlsafe(32)
    data = {'installation_id': str(uuid4()), 'name': 'Validation technique', 'android_version': '15',
            'app_version': '0.2.0', 'state': secrets.token_urlsafe(32), 'device_nonce': secrets.token_urlsafe(32),
            'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),
            'code_challenge_method': 'S256', 'redirect_uri': 'storyfx-android://auth/callback'}
    start = browser.post('/v1/auth/agent/start', json=data)
    assert start.status_code == 200
    query = parse_qs(urlparse(start.json()['connect_url']).query)
    assert set(query) == {'request_id'}
    request_id = query['request_id'][0]
    details = browser.get('/v1/auth/agent/request', params={'request_id': request_id})
    assert details.json()['name'] == 'Validation technique'
    authorized = browser.post('/v1/auth/agent/authorize', headers={'Origin': ORIGIN}, json={'request_id': request_id})
    query = parse_qs(urlparse(authorized.json()['redirect_to']).query)
    assert set(query) == {'ticket', 'state'}
    body = {key: data[key] for key in ('installation_id', 'state', 'device_nonce')}
    body.update(ticket=query['ticket'][0], code_verifier=verifier)
    return body


def test_cookie_encrypted_session_and_csrf(private):
    app, browser, _, _ = private
    response = login(browser)
    assert response.status_code == 200
    assert all(flag in response.headers['set-cookie'] for flag in ('Secure', 'HttpOnly', 'SameSite=lax'))
    assert 'access_token' not in response.text and 'refresh_token' not in response.text
    with app.state.store.transaction() as db:
        cipher = db.execute('SELECT ciphertext FROM auth_sessions').fetchone()[0]
        assert 'synthetic-password' not in cipher and 'refresh-owner-a' not in cipher
    assert browser.post('/v1/pairings', json={}).status_code == 403
    assert browser.post('/v1/auth/login', json={'email': 'a@b.c', 'password': 'private'}).status_code == 403


def test_pkce_ticket_nonce_replay_and_owner_revocation(private):
    app, browser, provider, _ = private
    assert login(browser).status_code == 200
    body = enroll(browser)
    wrong = {**body, 'code_verifier': secrets.token_urlsafe(32)}
    assert browser.post('/v1/auth/agent/exchange', json=wrong).status_code == 401
    result = browser.post('/v1/auth/agent/exchange', json=body)
    assert result.status_code == 200
    assert browser.post('/v1/auth/agent/exchange', json=body).status_code == 401
    token = result.json()['token']
    assert browser.post('/v1/agent/claim', headers={'Authorization': 'Bearer ' + token}, json={}).status_code == 200
    provider.denied.add('owner-a')
    assert browser.get('/v1/dashboard').status_code == 403
    assert browser.post('/v1/agent/claim', headers={'Authorization': 'Bearer ' + token}, json={}).status_code == 403


def test_tenant_isolation_and_device_revoke(private):
    _, browser, _, _ = private
    login(browser)
    device = browser.post('/v1/auth/agent/exchange', json=enroll(browser)).json()
    login(browser, 'owner-b')
    assert browser.get('/v1/dashboard').json()['devices'] == []
    assert browser.post('/v1/devices/' + device['device_id'] + '/revoke', headers={'Origin': ORIGIN}, json={}).status_code == 404
    login(browser)
    assert len(browser.get('/v1/dashboard').json()['devices']) == 1
    assert browser.post('/v1/devices/' + device['device_id'] + '/revoke', headers={'Origin': ORIGIN}, json={}).status_code == 200
    assert browser.post('/v1/agent/claim', headers={'Authorization': 'Bearer ' + device['token']}, json={}).status_code == 401


def test_one_refresh_session_survives_browser_logout(private):
    app, browser, provider, now = private
    login(browser)
    device = browser.post('/v1/auth/agent/exchange', json=enroll(browser)).json()
    now[0] += 3590
    assert browser.get('/v1/auth/session').status_code == 200
    assert provider.refreshes == 1
    assert browser.post('/v1/auth/logout', headers={'Origin': ORIGIN}, json={}).status_code == 200
    assert browser.get('/v1/auth/session').status_code == 401
    assert browser.post('/v1/agent/claim', headers={'Authorization': 'Bearer ' + device['token']}, json={}).status_code == 200
    assert provider.refreshes == 1
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM auth_sessions').fetchone()[0] == 1


def test_ticket_expiry_and_closed_payload(private):
    _, browser, _, now = private
    login(browser)
    body = enroll(browser)
    now[0] += 121
    assert browser.post('/v1/auth/agent/exchange', json=body).status_code == 401
    response = browser.post('/v1/auth/login', headers={'Origin': ORIGIN},
                            json={'email': 'owner-a@example.invalid', 'password': 'never-echo-this', 'role': 'owner'})
    assert response.status_code == 422 and 'never-echo-this' not in response.text


def test_reset_requires_recent_otp_and_proof_is_one_use(private):
    _, browser, _, now = private
    login(browser)
    body = {'password': 'synthetic-new-password', 'confirmation': 'synthetic-new-password'}
    assert browser.put('/v1/auth/password', headers={'Origin': ORIGIN}, json=body).status_code == 403
    otp = {'email': 'owner-a@example.invalid', 'code': '123456'}
    assert browser.post('/v1/auth/otp/verify', headers={'Origin': ORIGIN}, json=otp).status_code == 200
    assert browser.put('/v1/auth/password', headers={'Origin': ORIGIN}, json=body).status_code == 200
    assert browser.put('/v1/auth/password', headers={'Origin': ORIGIN}, json=body).status_code == 403
    browser.post('/v1/auth/otp/verify', headers={'Origin': ORIGIN}, json=otp)
    now[0] += 601
    assert browser.put('/v1/auth/password', headers={'Origin': ORIGIN}, json=body).status_code == 403


def test_sso_state_origin_nested_session_and_replay(private):
    _, browser, _, _ = private
    assert browser.post('/v1/auth/sso/start', json={}).status_code == 403
    start = browser.post('/v1/auth/sso/start', headers={'Origin': ORIGIN}, json={})
    query = parse_qs(urlparse(start.json()['redirect_to']).query)
    assert query['app'] == ['storyfx'] and query['return_to'] == [ORIGIN + '/auth/sso/callback']
    state = query['state'][0]
    callback = '/auth/sso/callback?code=' + secrets.token_urlsafe(32) + '&state=' + state
    assert browser.get(callback.replace(state, secrets.token_urlsafe(32))).status_code == 400
    response = browser.get(callback, follow_redirects=False)
    assert response.status_code == 303 and response.headers['location'] == '/login/?connected=1'
    assert browser.get('/v1/auth/session').status_code == 200
    assert browser.get(callback, follow_redirects=False).status_code == 400
