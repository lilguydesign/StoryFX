"""Split native receipts remain owner-scoped, immutable and usable by recipes."""
import json
from uuid import uuid4
import pytest
from test_private_auth import private
from test_control_android import setup
from test_control_center import HEADERS, add
from test_sequential_receipt import complete_diagnostics
from recipe_fixtures import action, launch, current
from storyfx_server.control_recipe_state import latest_verified_at


def completed_large_recipe(private, following=False):
    app, browser, _, now, auth, contact, _ = setup(private)
    contact = {**contact, 'app_version': '0.4.19', 'media_modes_ready': True}
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    name = 'Validation technique grand lot'
    add(browser, 'albums', name=name, count_per_post=11)
    add(browser, 'matrix', name=name, device='Validation technique', platform='WhatsApp',
        system='Validation technique', engine='multi', album2=name, count=11)
    snapshot = browser.get('/v1/control').json()
    rows = snapshot['collections']['matrix']
    ids = [row['id'] for row in rows if row['name'] == name]
    if following:
        ids += [row['id'] for row in rows if row['name'] != name]
    response = browser.post('/v1/control/recipes', headers=HEADERS, json={
        'client_key': str(uuid4()), 'revision': snapshot['revision'],
        'executor': 'android', 'row_ids': ids})
    assert response.status_code == 200, response.text
    recipe = response.json()
    assert action(browser, recipe, 'start').status_code == 200
    accepted = launch(browser, recipe)
    assert accepted.status_code == 200, accepted.text
    job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    assert job and job['payload']['count'] == 11
    response = browser.post('/v1/control/android/jobs/' + job['id'] + '/complete', headers=auth,
        json={'state': 'CONFIRMED', 'evidence': 'own_status_verified',
              'diagnostics': {**complete_diagnostics(), 'app_version': '0.4.19'}})
    assert response.status_code == 200, response.text
    return app, browser, now, recipe, job


def stored(app):
    with app.state.store.transaction() as db:
        return tuple(tuple(tuple(row) for row in db.execute('SELECT * FROM ' + table + ' ORDER BY job_id'))
                     for table in ('control_attempt_diagnostics', 'control_attempt_observations'))


def test_split_receipt_closes_recipe_without_republication_or_receipt_mutation(private):
    app, browser, _, recipe, job = completed_large_recipe(private)
    before = stored(app)
    assert 'sequential_proof' not in json.loads(before[0][0][-1])
    assert 'sequential_proof' in json.loads(before[1][0][-1])
    view = current(browser, recipe)
    assert view['state'] == 'PASSED' and view['all_steps_verified']
    with app.state.store.transaction() as db:
        assert latest_verified_at(db, 'owner-a') == db.execute(
            'SELECT completed FROM control_jobs WHERE id=?', (job['id'],)).fetchone()[0]
    released = action(browser, recipe, 'release')
    assert released.status_code == 200, released.text
    assert released.json()['state'] == 'RELEASED' and not released.json()['lock_held']
    assert len(browser.get('/v1/control').json()['reports']) == 1
    assert stored(app) == before


def test_split_receipt_enforces_full_five_minute_cooldown(private):
    app, browser, now, recipe, _ = completed_large_recipe(private, following=True)
    before = stored(app)
    assert current(browser, recipe)['state'] == 'COOLDOWN'
    now[0] += 299
    assert current(browser, recipe)['state'] == 'COOLDOWN'
    assert launch(browser, recipe, 1).json()['error'] == 'RECIPE_COOLDOWN'
    now[0] += 1
    assert current(browser, recipe)['state'] == 'READY'
    assert len(browser.get('/v1/control').json()['reports']) == 1
    assert stored(app) == before


def test_legacy_small_core_receipt_without_observations_still_passes(private):
    from recipe_fixtures import fixture, receipt
    app, browser, _, _, auth, _, recipe, _ = fixture(private, count=1)
    action(browser, recipe, 'start')
    launch(browser, recipe)
    job, _ = receipt(browser, auth)
    with app.state.store.transaction() as db:
        db.execute('DELETE FROM control_attempt_observations WHERE job_id=?', (job['id'],))
    before = stored(app)
    assert current(browser, recipe)['state'] == 'PASSED'
    assert action(browser, recipe, 'release').status_code == 200
    assert stored(app) == before


@pytest.mark.parametrize('change', ['missing', 'partial', 'foreign_owner', 'foreign_core'])
def test_missing_partial_or_foreign_proofs_never_advance_or_release(private, change):
    app, browser, _, recipe, job = completed_large_recipe(private)
    with app.state.store.transaction() as db:
        if change == 'missing':
            db.execute('DELETE FROM control_attempt_observations WHERE job_id=?', (job['id'],))
        elif change in ('foreign_owner', 'foreign_core'):
            table = 'control_attempt_observations' if change == 'foreign_owner' else 'control_attempt_diagnostics'
            db.execute('UPDATE ' + table + ' SET owner_id=? WHERE job_id=?', ('owner-b', job['id']))
        else:
            value = json.loads(db.execute('SELECT value FROM control_attempt_observations WHERE job_id=?',
                                         (job['id'],)).fetchone()[0])
            value['sequential_proof']['verified_counts'] = [9]
            db.execute('UPDATE control_attempt_observations SET value=? WHERE job_id=?',
                       (json.dumps(value), job['id']))
    before = stored(app)
    assert current(browser, recipe)['state'] == 'BLOCKED'
    with app.state.store.transaction() as db:
        assert latest_verified_at(db, 'owner-a') is None
        assert latest_verified_at(db, 'owner-b') is None
    assert action(browser, recipe, 'release').status_code == 409
    assert len(browser.get('/v1/control').json()['reports']) == 1
    assert stored(app) == before
