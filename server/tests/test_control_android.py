"""Native owner isolation, readiness, Windows concurrency and crash-safe queue tests."""
from datetime import datetime, timezone
from test_private_auth import private, login, enroll
from test_control_center import settings, executor, HEADERS


def setup(private):
    app, browser, provider, now = private
    login(browser); settings(browser)
    now[0] = datetime(2023, 11, 14, 13, tzinfo=timezone.utc).timestamp()
    exchange = browser.post('/v1/auth/agent/exchange', json=enroll(browser)).json()
    auth = {'Authorization': 'Bearer ' + exchange['token']}
    assert browser.post('/v1/control/android/bind', headers=auth,
                        json={'profile': 'Validation technique', 'enabled': True}).status_code == 200
    contact = {'service_ready': True, 'media_ready': True, 'screen_locked': False, 'app_version': '0.4.0'}
    return app, browser, provider, now, auth, contact, exchange['device_id']


def start(browser):
    revision = browser.get('/v1/control').json()['revision']
    return browser.post('/v1/control/scheduler/start', headers=HEADERS,
                        json={'revision': revision, 'profiles': ['Validation technique'],
                              'platforms': ['WhatsApp'], 'mode': 'manual', 'start_time': '05:00'})


def test_no_claim_before_visible_permissions_and_unlock(private):
    app, browser, _, _, auth, contact, _ = setup(private)
    assert browser.post('/v1/control/android/claim', headers=auth, json={}).status_code == 409
    for field in ('service_ready', 'media_ready'):
        response = browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact, field: False})
        assert response.status_code == 200 and not response.json()['ready']
        assert browser.post('/v1/control/android/claim', headers=auth, json={}).status_code == 409
    assert not browser.post('/v1/control/android/heartbeat', headers=auth,
                            json={**contact, 'screen_locked': True}).json()['ready']
    assert start(browser).status_code == 200
    assert browser.get('/v1/control').json()['reports'] == []
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    app.state.control_scheduler.tick()
    assert len(browser.get('/v1/control').json()['reports']) == 2


def test_native_preferred_over_windows_but_same_occurrence_never_replayed(private):
    app, browser, _, _, auth, contact, _ = setup(private)
    windows = executor(browser)
    browser.post('/v1/control/windows/heartbeat', headers=windows, json={'profiles': ['Validation technique']})
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    assert start(browser).status_code == 200
    assert browser.post('/v1/control/windows/claim', headers=windows, json={}).json()['job'] is None
    job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    assert job['payload']['execution_origin'] == 'web_android_agent'
    assert browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job'] is None
    path = '/v1/control/android/jobs/' + job['id']
    assert browser.post(path + '/ready', headers=auth, json={}).status_code == 200
    result = {'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain'}
    assert browser.post(path + '/complete', headers=auth, json=result).status_code == 200
    assert browser.post(path + '/complete', headers=auth, json=result).status_code == 200
    app.state.control_scheduler.tick()
    reports = browser.get('/v1/control').json()['reports']
    assert len(reports) == 2 and sum(r['state'] == 'NEEDS_REVIEW' for r in reports) == 1
    assert browser.post('/v1/control/windows/claim', headers=auth, json={}).status_code == 401


def test_stop_denies_final_action_but_late_result_is_preserved(private):
    _, browser, _, _, auth, contact, _ = setup(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact); start(browser)
    job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    path = '/v1/control/android/jobs/' + job['id']
    stopped = browser.post('/v1/control/stop', headers=HEADERS, json={'stop_scheduler': True}).json()
    assert stopped['running_stop_requested'] == 1
    assert browser.post(path + '/ready', headers=auth, json={}).status_code == 409
    assert browser.post(path + '/complete', headers=auth,
                        json={'state': 'CONFIRMED', 'evidence': 'own_status_verified'}).status_code == 200


def test_native_binding_cannot_read_technical_columns_or_other_owner(private):
    _, browser, provider, _, auth, contact, device = setup(private)
    data = browser.post('/v1/control/android/settings', headers=auth, json={}).json()
    assert all(set(row) == {'name', 'enabled'} for row in data['profiles'])
    assert browser.post('/v1/control/android/bind', headers=auth,
                        json={'profile': 'unknown', 'enabled': True}).status_code == 422
    login(browser, 'owner-b')
    assert browser.post('/v1/devices/' + device + '/revoke', headers=HEADERS, json={}).status_code == 404
    provider.denied.add('owner-a')
    assert browser.post('/v1/control/android/heartbeat', headers=auth, json=contact).status_code == 403


def test_duplicate_device_binding_and_stale_node_are_refused(private):
    _, browser, _, now, auth, contact, _ = setup(private)
    other = browser.post('/v1/auth/agent/exchange', json=enroll(browser)).json()
    other_auth = {'Authorization': 'Bearer ' + other['token']}
    assert browser.post('/v1/control/android/bind', headers=other_auth,
                        json={'profile': 'Validation technique', 'enabled': True}).status_code == 409
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact); start(browser)
    now[0] += 46
    assert browser.post('/v1/control/android/claim', headers=auth, json={}).status_code == 409
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    assert browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']


def test_native_results_require_coherent_proof_and_correct_device(private):
    _, browser, _, _, auth, contact, _ = setup(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact); start(browser)
    job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    path = '/v1/control/android/jobs/' + job['id']
    assert browser.post(path + '/complete', headers=auth,
                        json={'state': 'CONFIRMED', 'evidence': 'result_uncertain'}).status_code == 422
    other = browser.post('/v1/auth/agent/exchange', json=enroll(browser)).json()
    assert browser.post(path + '/complete', headers={'Authorization': 'Bearer ' + other['token']},
                        json={'state': 'CONFIRMED', 'evidence': 'own_status_verified'}).status_code == 409
    assert browser.get('/v1/control').json()['reports'][0]['state'] in ('QUEUED', 'CLAIMED')


def test_native_video_exclusion_and_missing_optional_album():
    from storyfx_server.control_android import executors
    native = {'connected': True, 'profiles': ['Validation technique'], 'executor': 'android_whatsapp_images_v1'}
    snapshot = {'nodes': [native]}
    value = {'device': 'Validation technique', 'platform': 'WhatsApp', 'engine': 'multi', 'count': 3,
             'system': 'Validation technique', 'album': 'Validation technique', 'album2': None}
    assert executors(snapshot, value) == [native]
    assert executors(snapshot, {**value, 'album': 'Video'}) == []
    assert executors(snapshot, {**value, 'engine': 'intro'}) == []
