"""Synthetic strict evidence, cooldown and restart-safe idempotency."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from test_private_auth import private
from test_control_center import HEADERS
from recipe_fixtures import fixture, action, launch, current, receipt


def test_one_explicit_step_and_persistent_cooldown_no_prequeue(private):
    app, browser, _, now, auth, contact, recipe, _ = fixture(private)
    assert action(browser, recipe, 'start').json()['state'] == 'READY'
    assert browser.get('/v1/control').json()['reports'] == []
    assert launch(browser, recipe, 1).json()['error'] == 'RECIPE_STEP_NOT_NEXT'
    key = str(uuid4())
    accepted = launch(browser, recipe, key=key).json()
    assert accepted['recipe']['state'] == 'IN_PROGRESS'
    assert launch(browser, recipe, key=key).json()['job_id'] == accepted['job_id']
    assert launch(browser, recipe, 1).json()['error'] == 'RECIPE_IN_PROGRESS'
    job, _ = receipt(browser, auth)
    assert job['occurrence_id'] not in {row['id'] for row in browser.get('/v1/control').json()['schedule']}
    assert 'original_occurrence' not in job['payload'] and 'retry_parent' not in job['payload']
    assert job['payload']['recipe_id'] == recipe['id']
    assert current(browser, recipe)['state'] == 'COOLDOWN'
    now[0] += 299
    broker = app.state.control_scheduler.broker
    from storyfx_server.control_recipes import Recipes
    broker.recipes = Recipes(broker)
    assert broker.recipes.read({'id': 'owner-a'}, recipe['id'])['state'] == 'COOLDOWN'
    assert launch(browser, recipe, 1).json()['error'] == 'RECIPE_COOLDOWN'
    assert launch(browser, recipe, 1, key=key).json()['error'] == 'RECIPE_IDEMPOTENCY_CONFLICT'
    now[0] += 1
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    assert current(browser, recipe)['state'] == 'READY'
    app.state.control_scheduler.tick()
    assert len(browser.get('/v1/control').json()['reports']) == 1
    assert launch(browser, recipe, 1).status_code == 200
    receipt(browser, auth)
    assert current(browser, recipe)['state'] == 'PASSED'


@pytest.mark.parametrize('state,proof,present', [
    ('NEEDS_REVIEW', 'none', True), ('FAILED_BEFORE_PUBLICATION', 'none', True),
    ('CONFIRMED', 'recent_rows', True), ('CONFIRMED', 'recent_visible', False)])
def test_uncertain_failed_or_incomplete_proof_never_advances(private, state, proof, present):
    _, browser, _, now, auth, contact, recipe, body = fixture(private)
    action(browser, recipe, 'start')
    accepted = launch(browser, recipe).json()
    receipt(browser, auth, state=state, proof=proof, with_diagnostics=present)
    now[0] += 3600
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    view = current(browser, recipe)
    assert view['state'] == 'BLOCKED' and not view['all_steps_verified']
    assert launch(browser, recipe, 1).json()['error'] == 'RECIPE_BLOCKED'
    assert launch(browser, recipe).json()['job_id'] == accepted['job_id']
    assert action(browser, recipe, 'release').status_code == 409
    assert browser.post('/v1/control/jobs/' + accepted['job_id'] + '/retry', headers=HEADERS,
                        json={'revision': body['revision']}).json()['error'] == 'MANUAL_RECIPE_ACTIVE'
    action(browser, recipe, 'cancel')
    assert action(browser, recipe, 'release').status_code == 200
    assert browser.post('/v1/control/jobs/' + accepted['job_id'] + '/retry', headers=HEADERS,
                        json={'revision': body['revision']}).status_code == 409


def test_two_concurrent_clicks_cannot_create_two_attempts(private):
    app, browser, _, _, _, _, recipe, _ = fixture(private, count=1)
    action(browser, recipe, 'start')
    service = app.state.control_scheduler.broker.recipes
    key = uuid4()
    def send(_):
        return service.launch({'id': 'owner-a'}, recipe['id'], recipe['steps'][0]['id'], key)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, range(2)))
    assert results[0]['job_id'] == results[1]['job_id']
    assert len(browser.get('/v1/control').json()['reports']) == 1


def test_old_native_version_and_changed_plan_are_refused(private):
    _, browser, _, _, auth, contact, recipe, _ = fixture(private, count=1)
    action(browser, recipe, 'start')
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact, 'app_version': '0.4.14'})
    assert launch(browser, recipe).json()['error'] == 'ANDROID_RECIPE_VERSION_REQUIRED'
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    from test_control_center import add
    add(browser, 'albums', name='Validation technique supplémentaire')
    assert launch(browser, recipe).json()['error'] == 'CONFIGURATION_CHANGED'
