"""Loopback-only synthetic API smoke. No tokens, device IDs or responses printed."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import httpx

BASE = 'http://127.0.0.1:18743'


def main():
    root = Path(__file__).resolve().parents[2]
    credential = (root / '.runtime' / 'private' / 'owner.credential').read_text().strip()
    owner = {'Authorization': 'Bearer ' + credential}
    with httpx.Client(base_url=BASE, timeout=10, follow_redirects=False) as api:
        health = api.get('/health')
        assert health.status_code == 200 and health.json()['publishing_enabled'] is False
        assert api.get('/v1/dashboard').status_code == 401
        code = api.post('/v1/pairings', headers=owner, json={}).json()['code']
        enrollment = api.post('/v1/devices/enroll', json={
            'code': code, 'installation_id': str(uuid4()), 'name': 'Validation technique',
            'android_version': 'simulation'}).json()
        agent = {'Authorization': 'Bearer ' + enrollment['token']}
        device_id = enrollment['device_id']
        assert api.post('/v1/devices/heartbeat', headers=agent, json={
            'battery_percent': 85, 'screen_locked': False,
            'app_version': '0.1.0', 'executor': 'diagnostic'}).status_code == 200
        now = datetime.now(timezone.utc)
        job_request = {'device_id': device_id, 'scheduled_at': now.isoformat(),
                       'expires_at': (now + timedelta(minutes=10)).isoformat()}
        scheduled = api.post('/v1/diagnostics', headers=owner, json=job_request)
        assert scheduled.status_code == 200
        assert api.post('/v1/diagnostics', headers=owner, json=job_request).json()['duplicate']
        job = api.post('/v1/agent/claim', headers=agent, json={}).json()['job']
        for stage in ('STARTED', 'DIAGNOSTIC_CONFIRMED'):
            body = {'event_id': str(uuid4()), 'lease_token': job['lease_token'],
                    'stage': stage, 'detail': 'diagnostic_only'}
            path = f"/v1/agent/jobs/{job['id']}/events"
            assert api.post(path, headers=agent, json=body).status_code == 200
            assert api.post(path, headers=agent, json=body).json()['duplicate']
        dashboard = api.get('/v1/dashboard', headers=owner).json()
        assert any(item['id'] == job['id'] and item['status'] == 'DIAGNOSTIC_CONFIRMED'
                   for item in dashboard['jobs'])
        preview = api.post('/v1/import-preview', headers=owner, json={})
        assert preview.status_code == 200 and preview.json()['activation_allowed'] is False
        assert api.get('/dashboard/').status_code == 200
        assert api.get('/dashboard/app.js').status_code == 200
        assert api.post(f'/v1/devices/{device_id}/revoke', headers=owner, json={}).status_code == 200
        assert api.post('/v1/agent/claim', headers=agent, json={}).status_code == 401
    print('LIVE_LOCAL_DIAGNOSTIC_SMOKE=passed; duplicate_events=deduplicated; publication=false')


if __name__ == '__main__':
    main()
