import unittest
import httpx
from storyfx_server.auth_client import AuthClient
from storyfx_server.password_help import password_help
from storyfx_server.store import DomainError


class PasswordHelpTests(unittest.TestCase):
    def test_statuses_use_only_existing_read(self):
        cases = [
            ({'is_member': True, 'has_existing_auth_user': True, 'password_status': 'password_exists'}, 'reset'),
            ({'is_member': True, 'has_existing_auth_user': True, 'password_status': 'password_not_set'}, 'create_verified'),
            ({'is_member': True, 'has_existing_auth_user': False, 'password_status': 'auth_user_missing', 'allow_create_password': True}, 'create'),
            ({'is_member': False, 'password_status': 'member_not_found'}, 'verify'),
            ({'is_member': True, 'password_status': 'disabled'}, None),
            ({'is_member': True, 'has_existing_auth_user': True}, None),
            ({'is_member': True, 'password_status': 'auth_user_missing'}, None),
        ]
        for response, expected in cases:
            calls = []
            def transport(request):
                calls.append(request)
                self.assertEqual(request.url.path, '/rest/v1/rpc/member_password_creation_guard_v1')
                return httpx.Response(200, json=response)
            client = AuthClient('synthetic', transport=httpx.MockTransport(transport))
            self.assertEqual(password_help(client, 'validation@example.invalid'), {'action': expected})
            self.assertEqual(len(calls), 1)
            client.http.close()

    def test_only_explicit_password_credentials_are_classified(self):
        for status, body, expected in [
            (400, {'error_code': 'invalid_credentials'}, 'PASSWORD_CREDENTIALS_INVALID'),
            (429, {'error_code': 'invalid_credentials'}, 'RATE_LIMITED'),
            (403, {'error_code': 'user_banned'}, 'AUTH_REFUSED'),
            (400, {'error_code': 'captcha_failed'}, 'AUTH_REFUSED'),
            (503, {}, 'AUTH_UNAVAILABLE'),
        ]:
            client = AuthClient('synthetic', transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body)))
            with self.assertRaises(DomainError) as caught:
                client.password('validation@example.invalid', 'old-platform-password')
            self.assertEqual(caught.exception.code, expected)
            client.http.close()


if __name__ == '__main__':
    unittest.main()
