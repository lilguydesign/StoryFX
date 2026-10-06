from test_private_auth import private
from test_control_android import setup, start
from test_control_center import HEADERS


def permission(browser, auth):
    return browser.post('/v1/control/android/unlock-authorized', headers=auth, json={})


def test_unlock_requires_due_plan_active_scheduler_and_unchanged_owner(private):
    app, browser, provider, _, auth, contact, _ = setup(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact,'screen_locked':True})
    assert permission(browser, auth).json() == {'authorized':False}
    assert start(browser).status_code == 200
    assert permission(browser, auth).json() == {'authorized':True}
    assert browser.get('/v1/control').json()['reports'] == []
    browser.post('/v1/control/scheduler/stop', headers=HEADERS, json={})
    assert permission(browser, auth).json() == {'authorized':False}
    provider.denied.add('owner-a')
    assert permission(browser, auth).status_code == 403


def test_unlock_refuses_missing_permissions_stale_heartbeat_and_no_credentials(private):
    _, browser, _, now, auth, contact, _ = setup(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact,'screen_locked':True})
    start(browser)
    assert permission(browser, {}).status_code == 401
    now[0] += 46
    assert permission(browser, auth).json() == {'authorized':False}
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact,'screen_locked':True,'media_ready':False})
    assert permission(browser, auth).json() == {'authorized':False}


def test_unlock_does_not_replay_claimed_uncertain_or_confirmed_jobs(private):
    _, browser, _, _, auth, contact, _ = setup(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    start(browser)
    for _ in range(2):
        job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
        browser.post('/v1/control/android/jobs/'+job['id']+'/complete', headers=auth,
                     json={'state':'NEEDS_REVIEW','evidence':'result_uncertain'})
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact,'screen_locked':True})
    assert permission(browser, auth).json() == {'authorized':False}


def test_unlock_covers_existing_queued_jobs_but_not_changed_catalog(private):
    _, browser, _, _, auth, contact, _ = setup(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    start(browser)
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact,'screen_locked':True})
    assert permission(browser, auth).json() == {'authorized':True}
    data = browser.get('/v1/control').json()
    browser.post('/v1/control/settings/profiles', headers=HEADERS,
                 json={'revision':data['revision'],'value':{'name':'Validation technique 2'}})
    assert permission(browser, auth).json() == {'authorized':False}


def test_unlock_does_not_wake_for_future_plan(private):
    _, browser, _, now, auth, contact, _ = setup(private)
    now[0] -= 13 * 3600
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact,'screen_locked':True})
    revision = browser.get('/v1/control').json()['revision']
    response = browser.post('/v1/control/scheduler/start', headers=HEADERS,
        json={'revision':revision,'profiles':['Validation technique'],'platforms':['WhatsApp'],
              'mode':'auto','start_time':'00:00'})
    assert response.status_code == 200
    assert permission(browser, auth).json() == {'authorized':False}
