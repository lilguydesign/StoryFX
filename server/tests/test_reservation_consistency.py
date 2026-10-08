"""Controlled snapshot races must not consume an occurrence on a changed executor."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from test_private_auth import private
from test_control_android import setup
from test_control_center import HEADERS, add, executor


@pytest.mark.parametrize('windows_fallback', [False, True])
def test_rebind_between_snapshot_and_reserve_revalidates_profile(private, monkeypatch, windows_fallback):
    app, browser, _, _, native, contact, _ = setup(private)
    add(browser, 'profiles', name='Validation technique 2')
    browser.post('/v1/control/android/heartbeat', headers=native, json=contact)
    windows = executor(browser) if windows_fallback else None
    if windows:
        browser.post('/v1/control/windows/heartbeat', headers=windows, json={'profiles': ['Validation technique']})
    snapshot = browser.get('/v1/control').json()
    broker = app.state.control_scheduler.broker
    original, captured, proceed = broker.snapshot, Event(), Event()

    def delayed(user):
        value = original(user)
        captured.set()
        assert proceed.wait(10)
        return value

    monkeypatch.setattr(broker, 'snapshot', delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(browser.post, '/v1/control/launch', headers=HEADERS,
                           json={'revision': snapshot['revision'], 'occurrence_id': snapshot['schedule'][0]['id']})
        try:
            assert captured.wait(10)
            changed = browser.post('/v1/control/android/bind', headers=native,
                                   json={'profile': 'Validation technique 2', 'enabled': True})
            assert changed.status_code == 200
            assert browser.post('/v1/control/android/heartbeat', headers=native, json=contact).json()['ready']
        finally:
            proceed.set()
        response = task.result(10)
    monkeypatch.setattr(broker, 'snapshot', original)
    assert browser.post('/v1/control/android/claim', headers=native, json={}).json()['job'] is None
    if windows:
        assert response.status_code == 200
        job = browser.post('/v1/control/windows/claim', headers=windows, json={}).json()['job']
        assert job['payload']['device'] == 'Validation technique'
        assert job['payload']['execution_origin'] == 'web_windows_bridge'
    else:
        assert response.status_code == 409 and response.json()['error'] == 'WINDOWS_EXECUTOR_UNAVAILABLE'
        assert browser.get('/v1/control').json()['reports'] == []


@pytest.mark.parametrize('change', ['windows_profile', 'android_permission', 'android_revoked', 'android_media'])
def test_reservation_rechecks_live_dispatch_permissions(private, change):
    from storyfx_server.control_publications import reserve
    from storyfx_server.store import DomainError
    app, browser, _, _, auth, contact, device = setup(private)
    if change == 'android_media':
        data = browser.get('/v1/control').json()
        row = data['collections']['matrix'][0]
        value = {key: item for key, item in row.items() if key != 'id'}
        result = browser.put('/v1/control/settings/matrix/' + row['id'], headers=HEADERS,
                             json={'revision': data['revision'], 'value': {**value, 'engine': 'intro', 'album': 'Validation technique'}})
        assert result.status_code == 200
        contact = {**contact, 'app_version': '0.4.15', 'media_modes_ready': True}
    if change == 'windows_profile':
        windows = executor(browser)
        browser.post('/v1/control/windows/heartbeat', headers=windows, json={'profiles': ['Validation technique']})
    else:
        browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    snapshot = browser.get('/v1/control').json()
    if change == 'windows_profile':
        browser.post('/v1/control/windows/heartbeat', headers=windows, json={'profiles': []})
    elif change == 'android_revoked':
        browser.post('/v1/devices/' + device + '/revoke', headers=HEADERS, json={})
    else:
        browser.post('/v1/control/android/heartbeat', headers=auth,
                     json={**contact, 'media_modes_ready': False} if change == 'android_media' else {**contact, 'service_ready': False})
    broker = app.state.control_scheduler.broker
    with pytest.raises(DomainError, match='WINDOWS_EXECUTOR_UNAVAILABLE'):
        reserve(broker, {'id': 'owner-a'}, snapshot, [snapshot['schedule'][0]])
    assert reserve(broker, {'id': 'owner-a'}, snapshot, [snapshot['schedule'][0]], strict=False) == []
    assert browser.get('/v1/control').json()['reports'] == []
