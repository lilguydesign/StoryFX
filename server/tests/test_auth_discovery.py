"""Runtime configuration discovery uses fixtures and never authenticates."""
import httpx
import pytest

from storyfx_server.auth_client import AuthClient
from storyfx_server.store import DomainError


CONFIG_URL = 'https://api.formafx.com/functions/v1/formafx-runtime-config'
FIXTURE_KEY = 'runtime-config-test-key'
CONFIG = {'SUPABASE_URL': 'https://api.formafx.com',
          'SUPABASE_ANON_KEY': FIXTURE_KEY}


def discovery_fixture(monkeypatch, payload):
    calls = []

    def read_config(url, **kwargs):
        assert url == CONFIG_URL
        calls.append(url)
        return httpx.Response(200, json=payload,
                              request=httpx.Request('GET', url))

    def authentication_forbidden(*args, **kwargs):
        pytest.fail('Authentication must not run during configuration discovery')

    monkeypatch.setattr(httpx, 'get', read_config)
    monkeypatch.setattr(httpx, 'post', authentication_forbidden)
    monkeypatch.setattr(httpx.Client, 'request', authentication_forbidden)
    return calls


def test_discover_uses_official_nested_runtime_configuration(monkeypatch):
    calls = discovery_fixture(monkeypatch, {'ok': True, 'config': CONFIG})
    client = AuthClient.discover()
    try:
        assert client.base == CONFIG['SUPABASE_URL']
        assert client.anon_key == FIXTURE_KEY
        assert calls == [CONFIG_URL]
    finally:
        client.http.close()


@pytest.mark.parametrize('payload', [
    {'ok': False, 'config': CONFIG},
    {'ok': True, **CONFIG},
    {'ok': True, 'config': {**CONFIG, 'SUPABASE_URL': 'https://other.invalid'}},
    {'ok': True, 'config': {**CONFIG, 'SUPABASE_ANON_KEY': ''}},
], ids=['unsuccessful-response', 'missing-nested-config', 'wrong-authority', 'empty-key'])
def test_discover_refuses_invalid_configuration_without_authentication(monkeypatch, payload):
    calls = discovery_fixture(monkeypatch, payload)
    with pytest.raises(DomainError, match='AUTH_UNAVAILABLE') as failure:
        AuthClient.discover()
    assert failure.value.status == 503
    assert calls == [CONFIG_URL]
