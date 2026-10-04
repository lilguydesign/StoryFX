from datetime import datetime, timezone
from pathlib import Path
import sys
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storyfx_server.api import create_app


OWNER = 'synthetic-validation-owner-' + 'x' * 40


@pytest.fixture
def lab(tmp_path):
    now = [datetime(2026, 10, 4, 10, tzinfo=timezone.utc).timestamp()]
    app = create_app(tmp_path / 'lab.db', OWNER, clock=lambda: now[0])
    with TestClient(app) as client:
        yield client, now, app


def auth(credential):
    return {'Authorization': 'Bearer ' + credential}


def enroll(client, installation=None, name='Validation technique'):
    code = client.post('/v1/pairings', json={}, headers=auth(OWNER)).json()['code']
    result = client.post('/v1/devices/enroll', json={
        'code': code, 'installation_id': installation or str(uuid4()),
        'name': name, 'android_version': '16'}).json()
    return result['device_id'], result['token']


def schedule(client, device_id, now, delta=0):
    return client.post('/v1/diagnostics', headers=auth(OWNER), json={
        'device_id': device_id,
        'scheduled_at': datetime.fromtimestamp(now + delta, timezone.utc).isoformat(),
        'expires_at': datetime.fromtimestamp(now + delta + 600, timezone.utc).isoformat()})


def event(client, credential, job, stage, identity=None):
    body = {'event_id': identity or str(uuid4()), 'lease_token': job['lease_token'],
            'stage': stage, 'detail': 'diagnostic_only'}
    return client.post(f"/v1/agent/jobs/{job['id']}/events", headers=auth(credential), json=body), body
