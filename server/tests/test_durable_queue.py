from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from conftest import OWNER, auth, enroll, event, schedule
from storyfx_server.api import create_app
from storyfx_server.jobs import claim


def test_scheduled_window_and_unique_occurrence(lab):
    client, now, _ = lab
    device, credential = enroll(client)
    first = schedule(client, device, now[0], delta=60).json()
    second = schedule(client, device, now[0], delta=60).json()
    assert first['job']['id'] == second['job']['id'] and second['duplicate']
    assert client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job'] is None
    now[0] += 60
    assert client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job']['id'] == first['job']['id']


def test_concurrent_claims_serialize_on_one_physical_device(lab):
    client, now, app = lab
    device, credential = enroll(client)
    schedule(client, device, now[0])
    schedule(client, device, now[0], delta=-1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        identity = app.state.store.device(credential)
        results = list(pool.map(lambda _: claim(app.state.store, identity)['job'], range(8)))
    assert sum(job is not None for job in results) == 1


def test_other_device_can_claim_while_first_is_busy(lab):
    client, now, app = lab
    first, first_credential = enroll(client)
    second, second_credential = enroll(client)
    schedule(client, first, now[0])
    schedule(client, second, now[0])
    assert claim(app.state.store, app.state.store.device(first_credential))['job'] is not None
    assert claim(app.state.store, app.state.store.device(second_credential))['job'] is not None


def test_event_outbox_retries_are_idempotent_and_conflicts_rejected(lab):
    client, now, _ = lab
    device, credential = enroll(client)
    schedule(client, device, now[0])
    job = client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job']
    result, body = event(client, credential, job, 'STARTED')
    assert result.status_code == 200
    url = f"/v1/agent/jobs/{job['id']}/events"
    duplicate = client.post(url, json=body, headers=auth(credential))
    assert duplicate.json()['duplicate'] is True
    assert client.post(url, json={**body, 'stage': 'DIAGNOSTIC_CONFIRMED'}, headers=auth(credential)).status_code == 409
    assert event(client, credential, job, 'DIAGNOSTIC_CONFIRMED')[0].status_code == 200
    assert client.get('/v1/dashboard', headers=auth(OWNER)).json()['metrics']['completed'] == 1


def test_expired_lease_is_reviewed_without_replay_then_late_outbox_resolves(lab):
    client, now, _ = lab
    device, credential = enroll(client)
    schedule(client, device, now[0])
    job = client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job']
    result, body = event(client, credential, job, 'STARTED')
    assert result.status_code == 200
    now[0] += 121
    dashboard = client.get('/v1/dashboard', headers=auth(OWNER)).json()
    assert dashboard['jobs'][0]['status'] == 'NEEDS_REVIEW'
    assert client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job'] is None
    # The old event remains acknowledged even after its lease has expired.
    assert client.post(f"/v1/agent/jobs/{job['id']}/events", json=body, headers=auth(credential)).json()['duplicate']
    assert event(client, credential, job, 'DIAGNOSTIC_CONFIRMED')[0].status_code == 200
    assert client.get('/v1/dashboard', headers=auth(OWNER)).json()['metrics']['completed'] == 1


def test_expired_queued_task_and_confirmation_before_start(lab):
    client, now, _ = lab
    device, credential = enroll(client)
    schedule(client, device, now[0])
    now[0] += 601
    assert client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job'] is None
    assert client.get('/v1/dashboard', headers=auth(OWNER)).json()['jobs'][0]['status'] == 'EXPIRED'
    schedule(client, device, now[0])
    job = client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job']
    assert event(client, credential, job, 'DIAGNOSTIC_CONFIRMED')[0].status_code == 409


def test_server_restart_preserves_inflight_and_completed_events(lab):
    client, now, app = lab
    device, credential = enroll(client)
    schedule(client, device, now[0])
    job = client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job']
    result, body = event(client, credential, job, 'STARTED')
    assert result.status_code == 200
    restarted = create_app(app.state.store.path, OWNER, clock=lambda: now[0])
    with TestClient(restarted) as other:
        assert other.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job'] is None
        assert other.post(f"/v1/agent/jobs/{job['id']}/events", json=body, headers=auth(credential)).json()['duplicate']
        assert event(other, credential, job, 'DIAGNOSTIC_CONFIRMED')[0].status_code == 200
        assert other.get('/v1/dashboard', headers=auth(OWNER)).json()['metrics']['completed'] == 1


def test_renewal_bounded_by_expiration_and_revocation_invalidates_outbox(lab):
    client, now, _ = lab
    device, credential = enroll(client)
    schedule(client, device, now[0])
    job = client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job']
    now[0] += 50
    response = client.post(f"/v1/agent/jobs/{job['id']}/renew", headers=auth(credential),
                           json={'lease_token': job['lease_token']})
    assert response.status_code == 200
    renewed = datetime.fromisoformat(response.json()['lease_expires_at']).timestamp()
    assert renewed == now[0] + 120
    client.post(f'/v1/devices/{device}/revoke', json={}, headers=auth(OWNER))
    assert event(client, credential, job, 'STARTED')[0].status_code == 401


def test_no_secrets_stored_in_database(lab):
    client, now, app = lab
    device, credential = enroll(client)
    schedule(client, device, now[0])
    job = client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job']
    with app.state.store.transaction() as db:
        dump = '\n'.join(db.iterdump())
    assert credential not in dump and job['lease_token'] not in dump and OWNER not in dump


def test_owner_can_cancel_ambiguous_diagnostic_and_release_queue(lab):
    client, now, _ = lab
    device, credential = enroll(client)
    schedule(client, device, now[0])
    first = client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job']
    now[0] += 121
    schedule(client, device, now[0])
    assert client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job'] is None
    path = f"/v1/jobs/{first['id']}/cancel"
    assert client.post(path, json={}, headers=auth(credential)).status_code == 401
    assert client.post(path, json={}, headers=auth(OWNER)).status_code == 200
    assert event(client, credential, first, 'STARTED')[0].status_code == 409
    assert client.post('/v1/agent/claim', json={}, headers=auth(credential)).json()['job'] is not None
