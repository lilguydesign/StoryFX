"""Validation scopes cannot authorize other rows or replay the paused interval."""
from uuid import uuid4
from test_private_auth import private
from test_control_center import HEADERS, add
from recipe_fixtures import ROOT, fixture, action, launch, receipt


def restart(browser, revision, mode='auto', platforms=None):
    return browser.post('/v1/control/scheduler/start', headers=HEADERS, json={
        'revision': revision, 'profiles': ['Validation technique'],
        'platforms': platforms or ['WhatsApp'], 'mode': mode, 'start_time': '00:00'})


def test_pass_release_never_starts_auto_and_future_resume_has_no_catchup(private):
    app, browser, _, now, auth, _, recipe, body = fixture(private, count=1)
    action(browser, recipe, 'start')
    launch(browser, recipe)
    receipt(browser, auth)
    ended = now[0]
    released = action(browser, recipe, 'release').json()
    assert released['all_steps_verified'] and not released['lock_held']
    assert not browser.get('/v1/control').json()['scheduler']['enabled']
    assert action(browser, recipe, 'release').json() == released
    assert restart(browser, body['revision'], 'manual').json()['error'] == 'RECIPE_FUTURE_AUTO_REQUIRED'
    assert restart(browser, body['revision']).status_code == 200
    with app.state.store.transaction() as db:
        scheduler = db.execute('SELECT * FROM control_schedulers').fetchone()
        assert scheduler['from_at'] >= ended + 300
        assert db.execute('SELECT COUNT(*) FROM control_jobs').fetchone()[0] == 1
    app.state.control_scheduler.tick()
    assert len(browser.get('/v1/control').json()['reports']) == 1


def test_subset_recipe_cannot_authorize_other_rows_or_revised_configuration(private):
    _, browser, _, _, auth, _, _, body = fixture(private)
    recipe = browser.post(ROOT, headers=HEADERS, json={**body, 'client_key': str(uuid4()),
                          'row_ids': body['row_ids'][:1]}).json()
    action(browser, recipe, 'start')
    launch(browser, recipe)
    receipt(browser, auth)
    action(browser, recipe, 'release')
    assert restart(browser, body['revision']).json()['error'] == 'RECIPE_SCOPE_NOT_VALIDATED'
    changed = add(browser, 'albums', name='Validation technique nouvelle révision')
    assert restart(browser, changed['revision']).json()['error'] == 'RECIPE_SCOPE_NOT_VALIDATED'


def test_recipe_scope_cannot_authorize_facebook(private):
    _, browser, _, _, auth, _, _, body = fixture(private, count=1)
    changed = add(browser, 'matrix', name='Validation technique Facebook', device='Validation technique',
                  platform='Facebook', system='Validation technique', engine='multi', album2='Validation technique',
                  count=3, page='CM', page_name='Validation technique page')
    recipe = browser.post(ROOT, headers=HEADERS, json={**body, 'client_key': str(uuid4()),
                          'revision': changed['revision']}).json()
    action(browser, recipe, 'start')
    launch(browser, recipe)
    receipt(browser, auth)
    action(browser, recipe, 'release')
    assert restart(browser, changed['revision'], platforms=['WhatsApp', 'Facebook']).json()['error'] == 'RECIPE_SCOPE_NOT_VALIDATED'


def test_cancel_draft_does_not_disable_or_change_an_existing_scheduler(private):
    app, browser, _, _, _, _, recipe, body = fixture(private, count=1)
    assert restart(browser, body['revision']).status_code == 200
    with app.state.store.transaction() as db:
        before = dict(db.execute('SELECT * FROM control_schedulers').fetchone())
    action(browser, recipe, 'cancel')
    action(browser, recipe, 'release')
    with app.state.store.transaction() as db:
        after = dict(db.execute('SELECT * FROM control_schedulers').fetchone())
        assert before == after
        assert not db.execute('SELECT * FROM control_recipe_boundaries').fetchone()


def test_cooldown_cannot_be_bypassed_by_a_new_recipe(private):
    _, browser, _, now, auth, contact, recipe, body = fixture(private, count=1)
    action(browser, recipe, 'start')
    launch(browser, recipe)
    receipt(browser, auth)
    action(browser, recipe, 'release')
    following = browser.post(ROOT, headers=HEADERS, json={**body, 'client_key': str(uuid4())}).json()
    assert action(browser, following, 'start').json()['state'] == 'COOLDOWN'
    assert launch(browser, following).json()['error'] == 'RECIPE_COOLDOWN'
    now[0] += 299
    assert launch(browser, following).json()['error'] == 'RECIPE_COOLDOWN'
    now[0] += 1
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    assert launch(browser, following).status_code == 200


def test_cancelling_another_draft_cannot_remove_active_lock_or_modify_scheduler(private):
    app, browser, _, _, _, _, recipe, body = fixture(private, count=1)
    restart(browser, body['revision'])
    action(browser, recipe, 'start')
    other = browser.post(ROOT, headers=HEADERS, json={**body, 'client_key': str(uuid4())}).json()
    action(browser, other, 'cancel')
    assert action(browser, other, 'release').status_code == 200
    with app.state.store.transaction() as db:
        assert db.execute('SELECT recipe_id FROM control_recipe_locks').fetchone()[0] == recipe['id']
        assert db.execute('SELECT enabled FROM control_schedulers').fetchone()[0] == 1
