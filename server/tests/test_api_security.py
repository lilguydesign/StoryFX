from uuid import uuid4
from conftest import OWNER, auth, enroll, event, schedule
import pytest
from storyfx_server.devices import heartbeat
from storyfx_server.models import Heartbeat
from storyfx_server.store import DomainError


def test_owner_and_device_permissions_are_separate(lab):
    client, _, _ = lab
    assert client.get('/v1/dashboard').status_code == 401
    _, credential = enroll(client)
    assert client.get('/v1/dashboard', headers=auth(credential)).status_code == 401
    assert client.post('/v1/agent/claim', json={}, headers=auth(OWNER)).status_code == 401


def test_one_time_enrollment_expiry_and_no_credentials_in_dashboard(lab):
    client, now, _ = lab
    code = client.post('/v1/pairings', json={}, headers=auth(OWNER)).json()['code']
    body = {'code': code, 'installation_id': str(uuid4()), 'name': 'Validation technique', 'android_version': '16'}
    enrolled = client.post('/v1/devices/enroll', json=body)
    assert enrolled.status_code == 200
    assert client.post('/v1/devices/enroll', json=body).status_code == 400
    dashboard = client.get('/v1/dashboard', headers=auth(OWNER)).text
    assert enrolled.json()['token'] not in dashboard and body['installation_id'] not in dashboard
    fresh = client.post('/v1/pairings', json={}, headers=auth(OWNER)).json()['code']
    now[0] += 601
    assert client.post('/v1/devices/enroll', json={**body, 'code': fresh}).status_code == 400


def test_same_installation_rotates_credential_and_keeps_identity(lab):
    client, _, _ = lab
    installation = str(uuid4())
    first_id, first = enroll(client, installation)
    second_id, second = enroll(client, installation)
    assert first_id == second_id and first != second
    assert client.post('/v1/agent/claim', json={}, headers=auth(first)).status_code == 401
    assert client.post('/v1/agent/claim', json={}, headers=auth(second)).status_code == 200
    assert client.get('/v1/dashboard', headers=auth(OWNER)).json()['metrics']['devices'] == 1


def test_device_revocation_cancels_future_jobs_and_denies_access(lab):
    client, now, _ = lab
    device, credential = enroll(client)
    assert schedule(client, device, now[0]).status_code == 200
    assert client.post(f'/v1/devices/{device}/revoke', json={}, headers=auth(OWNER)).status_code == 200
    assert client.post('/v1/agent/claim', json={}, headers=auth(credential)).status_code == 401
    assert client.get('/v1/dashboard', headers=auth(OWNER)).json()['jobs'][0]['status'] == 'CANCELLED'


def test_cross_device_events_rejected_and_no_arbitrary_action(lab):
    client, now, _ = lab
    first_device, first = enroll(client)
    _, second = enroll(client)
    schedule(client, first_device, now[0])
    job = client.post('/v1/agent/claim', json={}, headers=auth(first)).json()['job']
    assert event(client, second, job, 'STARTED')[0].status_code == 409
    result, _ = event(client, first, job, 'PUBLISH')
    assert result.status_code == 422
    assert job['lease_token'] not in result.text
    assert client.post('/v1/publish', json={}, headers=auth(OWNER)).status_code == 404


def test_request_validation_does_not_echo_pairing_secrets(lab):
    client, _, _ = lab
    synthetic = 'private-validation-value'
    result = client.post('/v1/devices/enroll', json={'code': synthetic})
    assert result.status_code == 422 and synthetic not in result.text


def test_naive_times_unknown_fields_and_expired_tasks_rejected(lab):
    client, _, _ = lab
    device, _ = enroll(client)
    body = {'device_id': device, 'scheduled_at': '2026-10-04T11:00:00', 'expires_at': '2026-10-04T12:00:00'}
    assert client.post('/v1/diagnostics', json=body, headers=auth(OWNER)).status_code == 422
    body.update(scheduled_at='2026-10-04T11:00:00Z', expires_at='2026-10-04T12:00:00Z', command='shell')
    assert client.post('/v1/diagnostics', json=body, headers=auth(OWNER)).status_code == 422


def test_pairing_rate_limit_and_security_headers(lab):
    client, _, _ = lab
    for _ in range(20):
        assert client.post('/v1/pairings', json={}, headers=auth(OWNER)).status_code == 200
    assert client.post('/v1/pairings', json={}, headers=auth(OWNER)).status_code == 429
    health = client.get('/health')
    assert health.json()['publishing_enabled'] is False
    assert health.headers['Cache-Control'] == 'no-store'
    assert "frame-ancestors 'none'" in health.headers['Content-Security-Policy']


def test_rotation_between_authentication_and_write_is_rejected(lab):
    client, _, app = lab
    installation = str(uuid4())
    _, credential = enroll(client, installation)
    stale_identity = app.state.store.device(credential)
    enroll(client, installation)
    body = Heartbeat(battery_percent=70, screen_locked=False, executor='diagnostic', app_version='0.1.0')
    with pytest.raises(DomainError) as caught:
        heartbeat(app.state.store, stale_identity, body)
    assert caught.value.status == 401


def test_unicode_credentials_do_not_raise_an_internal_error(lab):
    client, _, _ = lab
    # UTF-8 raw header verifies unexpected bearer values still fail closed.
    result = client.get('/v1/dashboard', headers={b'Authorization': 'Bearer é'.encode('utf-8')})
    assert result.status_code == 401


def test_chunked_and_misdeclared_request_size_is_bounded(lab):
    client, _, _ = lab
    assert client.post('/v1/pairings', content=iter([b'x' * 9000, b'y' * 9000]),
                       headers=auth(OWNER)).status_code == 413
    assert client.post('/v1/pairings', content=b'x' * 18000,
                       headers={**auth(OWNER), 'content-length': '1'}).status_code == 413
