"""FormaFX is the identity authority; this client never creates an account."""
import time
import httpx
from .store import DomainError


class AuthClient:
    base = 'https://api.formafx.com'

    def __init__(self, anon_key, transport=None, clock=time.time):
        self.anon_key, self.clock = anon_key, clock
        self.http = httpx.Client(timeout=15, follow_redirects=False, transport=transport)

    @classmethod
    def discover(cls):
        try:
            response = httpx.get(cls.base + '/functions/v1/formafx-runtime-config', timeout=15)
            response.raise_for_status()
            config = response.json()
            if config.get('SUPABASE_URL', '').rstrip('/') != cls.base:
                raise ValueError()
            key = config['SUPABASE_ANON_KEY']
            if not isinstance(key, str) or not key:
                raise ValueError()
            return cls(key)
        except (httpx.HTTPError, KeyError, ValueError):
            raise DomainError('AUTH_UNAVAILABLE', 503) from None

    def call(self, method, path, body=None, access=None):
        headers = {'apikey': self.anon_key, 'Content-Type': 'application/json'}
        if access:
            headers['Authorization'] = f'Bearer {access}'
        try:
            response = self.http.request(method, self.base + path, headers=headers, json=body)
            if response.status_code == 429:
                raise DomainError('RATE_LIMITED', 429)
            if response.status_code in (400, 401, 403, 422):
                raise DomainError('AUTH_REFUSED', 401)
            if response.status_code >= 300:
                raise DomainError('AUTH_UNAVAILABLE', 503)
            return response.json() if response.content else {}
        except (httpx.HTTPError, ValueError):
            raise DomainError('AUTH_UNAVAILABLE', 503) from None

    def password(self, email, password):
        return self.tokens(self.call('POST', '/auth/v1/token?grant_type=password',
                                    {'email': email, 'password': password}))

    def refresh(self, refresh):
        return self.tokens(self.call('POST', '/auth/v1/token?grant_type=refresh_token',
                                    {'refresh_token': refresh}))

    def verify_otp(self, email, code):
        return self.tokens(self.call('POST', '/auth/v1/verify',
                                    {'email': email, 'token': code, 'type': 'email'}))

    def request_otp(self, email):
        eligible = self.call('POST', '/rest/v1/rpc/auth_email_can_request_otp_v1',
                             {'p_email': email}, self.anon_key)
        if not isinstance(eligible, dict) or eligible.get('allowed') is not True:
            # A uniform result avoids revealing membership from the StoryFX form.
            return
        self.call('POST', '/auth/v1/otp', {'email': email, 'create_user': False})

    def owner(self, access):
        user = self.call('GET', '/auth/v1/user', access=access)
        allowed = self.call('POST', '/rest/v1/rpc/storyfx_owner_allowed_v1', {}, access)
        if allowed is not True or not user.get('id') or not user.get('email'):
            raise DomainError('OWNER_ACCESS_REQUIRED', 403)
        return {'id': user['id'], 'email': user['email']}

    def tokens(self, payload):
        if not isinstance(payload, dict):
            raise DomainError('AUTH_UNAVAILABLE', 503)
        required = ('access_token', 'refresh_token')
        if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
            raise DomainError('AUTH_UNAVAILABLE', 503)
        user = self.owner(payload['access_token'])
        return {**user, **{key: payload[key] for key in required},
                'expires_at': int(payload.get('expires_at') or self.clock() + payload.get('expires_in', 3600))}
