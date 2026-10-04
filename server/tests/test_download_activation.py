"""Activation must tolerate transient gateways, never authentication or bad assets."""
import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

spec = importlib.util.spec_from_file_location(
    'download_installer', Path(__file__).resolve().parents[2] / 'deploy/install_download.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def response(**overrides):
    payload = {'ok': True, 'sha256': installer.SHA, 'download_url': installer.URL,
               'publishing_enabled': False, **overrides}
    return io.BytesIO(json.dumps(payload).encode())


def test_transient_schema_gateway_recovers():
    replies = iter([HTTPError('https://example.invalid', 503, 'transient', {}, None), response()])
    pauses = []

    def open_url(*args, **kwargs):
        item = next(replies)
        if isinstance(item, Exception):
            raise item
        return item

    installer.verify_metadata('https://example.invalid', open_url, pauses.append)
    assert pauses == [1]


def test_authentication_failure_is_immediate():
    pauses = []

    def open_url(*args, **kwargs):
        raise HTTPError('https://example.invalid', 401, 'authentication', {}, None)

    with pytest.raises(HTTPError):
        installer.verify_metadata('https://example.invalid', open_url, pauses.append)
    assert pauses == []


@pytest.mark.parametrize('overrides', [
    {'sha256': '0' * 64}, {'download_url': 'https://example.invalid/app.apk'},
    {'publishing_enabled': True},
])
def test_wrong_asset_contract_is_never_retried(overrides):
    pauses = []
    with pytest.raises(AssertionError):
        installer.verify_metadata('https://example.invalid', lambda *a, **k: response(**overrides), pauses.append)
    assert pauses == []
