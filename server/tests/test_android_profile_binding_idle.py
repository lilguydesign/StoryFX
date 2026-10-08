"""Permission changes never cancel a queue or discard an in-flight receipt."""
from uuid import uuid4
import pytest
from test_private_auth import private
from android_profile_fixtures import ROOT, fixture, associate, remove, internals, pending


@pytest.mark.parametrize('state', ['QUEUED', 'CLAIMED', 'CANCEL_REQUESTED', 'NEEDS_REVIEW'])
def test_all_pending_states_block_mutations_without_changing_jobs(private, state):
    app, browser, _, _, auth, _, body = fixture(private)
    binding = associate(browser, body).json()
    pending(app, body, state)
    before = internals(app)
    profiles = browser.get('/v1/control').json()['collections']['profiles']
    other = next(row for row in profiles if row['name'] == 'Validation technique 3')
    assert associate(browser, {**body, 'client_key': str(uuid4()), 'profile_id': other['id']}).json()['error'] == 'PUBLICATION_IN_PROGRESS'
    assert remove(browser, binding, body['revision']).json()['error'] == 'PUBLICATION_IN_PROGRESS'
    assert browser.post('/v1/control/android/bind', headers=auth,
                        json={'profile': 'Validation technique', 'enabled': False}).json()['error'] == 'PUBLICATION_IN_PROGRESS'
    # Idempotent reads remain possible while work is pending; readiness is not reset.
    assert associate(browser, body).json() == binding
    same = browser.post('/v1/control/android/bind', headers=auth,
                        json={'profile': 'Validation technique', 'enabled': True})
    assert same.status_code == 200 and same.json()['authorized_profiles'][0]['ready'] is True
    assert internals(app) == before


def test_late_receipt_survives_refused_permission_change(private):
    app, browser, _, now, auth, _, body = fixture(private)
    binding = associate(browser, body).json()
    identity = pending(app, body, 'CLAIMED')
    now[0] += 901
    assert browser.get('/v1/control').json()['reports'][0]['state'] == 'NEEDS_REVIEW'
    assert remove(browser, binding, body['revision']).json()['error'] == 'PUBLICATION_IN_PROGRESS'
    assert browser.post('/v1/control/android/jobs/' + identity + '/complete', headers=auth,
                        json={'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain'}).status_code == 200
    assert remove(browser, binding, body['revision']).status_code == 200
    report = browser.get('/v1/control').json()['reports'][0]
    assert report['state'] == 'NEEDS_REVIEW' and report['completed_at']
    assert len(browser.get('/v1/control').json()['reports']) == 1


def test_recipe_lock_and_diagnostic_activity_refuse_permission_change(private):
    from test_control_center import HEADERS
    app, browser, _, now, _, _, body = fixture(private)
    snapshot = browser.get('/v1/control').json()
    recipe = browser.post('/v1/control/recipes', headers=HEADERS, json={
        'client_key': str(uuid4()), 'revision': snapshot['revision'], 'executor': 'android',
        'row_ids': [snapshot['collections']['matrix'][0]['id']]}).json()
    assert browser.post('/v1/control/recipes/' + recipe['id'] + '/start', headers=HEADERS, json={}).status_code == 200
    assert associate(browser, body).json()['error'] == 'MANUAL_RECIPE_ACTIVE'
    assert browser.post('/v1/control/recipes/' + recipe['id'] + '/cancel', headers=HEADERS, json={}).status_code == 200
    assert browser.post('/v1/control/recipes/' + recipe['id'] + '/release', headers=HEADERS, json={}).status_code == 200
    from datetime import datetime, timezone
    response = browser.post('/v1/diagnostics', headers=HEADERS, json={
        'device_id': body['device_id'], 'scheduled_at': datetime.fromtimestamp(now[0], timezone.utc).isoformat(),
        'expires_at': datetime.fromtimestamp(now[0] + 600, timezone.utc).isoformat()})
    assert response.status_code == 200
    assert associate(browser, body).json()['error'] == 'DEVICE_ACTIVITY_IN_PROGRESS'
    assert browser.get(ROOT).json()['bindings'] == []
