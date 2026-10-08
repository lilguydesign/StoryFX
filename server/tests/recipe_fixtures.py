"""Synthetic native validation plans; no Appium, devices or provider calls."""
from uuid import uuid4
from test_control_android import setup
from test_control_center import HEADERS, add
from test_attempt_diagnostics import diagnostics

ROOT = '/v1/control/recipes'


def fixture(private, count=2):
    app, browser, provider, now, auth, contact, _ = setup(private)
    contact = {**contact, 'app_version': '0.4.15', 'media_modes_ready': True}
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    for index in range(2, count + 1):
        name = 'Validation technique ' + str(index)
        add(browser, 'albums', name=name, count_per_post=3)
        add(browser, 'matrix', name=name, device='Validation technique', platform='WhatsApp',
            system='Validation technique', engine='multi', album2=name, count=3)
    snapshot = browser.get('/v1/control').json()
    body = {'client_key': str(uuid4()), 'revision': snapshot['revision'], 'executor': 'android',
            'row_ids': [row['id'] for row in snapshot['collections']['matrix']]}
    response = browser.post(ROOT, headers=HEADERS, json=body)
    assert response.status_code == 200, response.text
    return app, browser, provider, now, auth, contact, response.json(), body


def action(browser, recipe, verb, body=None):
    return browser.post(ROOT + '/' + recipe['id'] + '/' + verb, headers=HEADERS, json=body or {})


def launch(browser, recipe, position=0, key=None):
    return action(browser, recipe, 'steps/' + recipe['steps'][position]['id'] + '/launch',
                  {'client_key': key or str(uuid4())})


def current(browser, recipe):
    return browser.get(ROOT + '/' + recipe['id']).json()


def receipt(browser, auth, state='CONFIRMED', proof='recent_visible', with_diagnostics=True):
    response = browser.post('/v1/control/android/claim', headers=auth, json={})
    assert response.status_code == 200, response.text
    job = response.json()['job']
    assert job
    value = {'state': state, 'evidence': {'CONFIRMED': 'own_status_verified',
             'NEEDS_REVIEW': 'result_uncertain', 'FAILED_BEFORE_PUBLICATION': 'album_media_unavailable'}[state]}
    if with_diagnostics:
        value['diagnostics'] = {**diagnostics(), 'app_version': '0.4.15', 'verification_method': proof}
    response = browser.post('/v1/control/android/jobs/' + job['id'] + '/complete', headers=auth, json=value)
    assert response.status_code == 200, response.text
    return job, value
