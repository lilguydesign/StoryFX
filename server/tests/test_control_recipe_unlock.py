"""Synthetic permissions only: no PIN, phone action, scheduler resumption or send."""
import json
import pytest
from test_private_auth import private, login
from test_control_center import add
from test_control_unlock import permission
from recipe_fixtures import fixture, action, launch


def prepared(private, start=True):
    app, browser, provider, now, auth, contact, recipe, _ = fixture(private, count=1)
    contact = {**contact, 'app_version': '0.4.18', 'screen_locked': True}
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    if start:
        assert action(browser, recipe, 'start').json()['state'] == 'READY'
    return app, browser, provider, now, auth, contact, recipe


def test_explicit_start_allows_exact_phone_without_enabling_or_enqueuing(private):
    app, browser, _, _, auth, _, recipe = prepared(private, start=False)
    assert permission(browser, auth).json() == {'authorized': False}
    assert action(browser, recipe, 'start').json()['state'] == 'READY'
    tables = ('control_jobs', 'control_recipes', 'control_recipe_steps', 'control_recipe_locks',
              'control_recipe_boundaries', 'control_schedulers', 'control_items')
    def business_state():
        with app.state.store.transaction() as db:
            return {table: [tuple(row) for row in db.execute('SELECT * FROM ' + table)] for table in tables}
    before = business_state()
    for _ in range(2):
        assert permission(browser, auth).json() == {'authorized': True}
    assert business_state() == before
    with app.state.store.transaction() as db:
        assert db.execute('SELECT count(*) FROM control_jobs').fetchone()[0] == 0
        assert not db.execute('SELECT 1 FROM control_schedulers WHERE enabled=1').fetchone()


@pytest.mark.parametrize('elapsed', [-1, 90, 1000])
def test_start_window_is_bounded_and_cannot_be_extended_by_repeated_start(private, elapsed):
    _, browser, _, now, auth, contact, recipe = prepared(private)
    now[0] += elapsed
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    action(browser, recipe, 'start')
    assert permission(browser, auth).json() == {'authorized': False}


@pytest.mark.parametrize('verb', ['cancel', 'release'])
def test_cancelled_or_released_recipe_cannot_unlock(private, verb):
    _, browser, _, _, auth, _, recipe = prepared(private)
    action(browser, recipe, 'cancel')
    if verb == 'release':
        assert action(browser, recipe, 'release').status_code == 200
    assert permission(browser, auth).json() == {'authorized': False}


def test_revoked_owner_and_other_owner_cannot_gain_permission(private):
    _, browser, provider, _, auth, _, _ = prepared(private)
    assert permission(browser, {}).status_code == 401
    login(browser, 'owner-b')
    # The agent's original owner is used, never the current browser's identity.
    assert permission(browser, auth).json() == {'authorized': True}
    provider.denied.add('owner-a')
    assert permission(browser, auth).status_code == 403


@pytest.mark.parametrize('field,value', [('service_ready', False), ('media_ready', False),
                                       ('media_modes_ready', False), ('app_version', '0.4.17')])
def test_missing_capability_or_stale_device_refused(private, field, value):
    _, browser, _, now, auth, contact, _ = prepared(private)
    # Use an intro mode to require the media-v2 capability, as real video lots do.
    app = private[0]
    with app.state.store.transaction() as db:
        row = db.execute('SELECT id,publication FROM control_recipe_steps').fetchone()
        publication = json.loads(row['publication'])
        publication['engine'] = 'intro'
        db.execute('UPDATE control_recipe_steps SET publication=? WHERE id=?', (json.dumps(publication), row['id']))
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact, field: value})
    assert permission(browser, auth).json() == {'authorized': False}
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    now[0] += 45
    assert permission(browser, auth).json() == {'authorized': False}


def test_changed_catalog_or_different_profile_is_refused(private):
    app, browser, _, _, auth, _, _ = prepared(private)
    with app.state.store.transaction() as db:
        db.execute("UPDATE control_android_links SET profile='Other synthetic profile'")
    assert permission(browser, auth).json() == {'authorized': False}
    with app.state.store.transaction() as db:
        db.execute("UPDATE control_android_links SET profile='Validation technique'")
    add(browser, 'albums', name='Validation technique changed')
    assert permission(browser, auth).json() == {'authorized': False}


def test_any_launched_step_disables_manual_unlock_even_after_completion(private):
    app, browser, _, _, auth, contact, recipe = prepared(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact, 'screen_locked': False})
    assert launch(browser, recipe).status_code == 200
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    assert permission(browser, auth).json() == {'authorized': False}
    with app.state.store.transaction() as db:
        db.execute("UPDATE control_jobs SET state='NEEDS_REVIEW',completed=created")
    assert permission(browser, auth).json() == {'authorized': False}


def test_installation_hold_and_cooldown_block_wake(private):
    app, browser, _, now, auth, _, _ = prepared(private)
    with app.state.store.transaction() as db:
        db.execute('INSERT INTO android_installation_holds VALUES (?,?,?,?,NULL,NULL)',
                   ('synthetic-operation', 'owner-a', 'synthetic-targets', now[0]))
    assert permission(browser, auth).json() == {'authorized': False}
    with app.state.store.transaction() as db:
        db.execute('UPDATE android_installation_holds SET released=?', (now[0],))
        db.execute('UPDATE control_recipe_boundaries SET not_before=?', (now[0] + 300,))
    assert permission(browser, auth).json() == {'authorized': False}


def test_active_recipe_never_falls_back_to_scheduled_unlock(private):
    app, browser, _, _, auth, _, _ = prepared(private)
    with app.state.store.transaction() as db:
        db.execute("UPDATE control_recipes SET started=started-100")
        # A stale recipe remains an exclusion, even if a scheduler row exists.
        db.execute("INSERT INTO control_schedulers VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ('owner-a', 1, 'synthetic-generation', 'synthetic-session', 0, '{}', 0, 'manual', 0, ''))
    assert permission(browser, auth).json() == {'authorized': False}


def test_enabled_scheduler_refused_even_with_fresh_manual_start(private):
    app, browser, _, _, auth, _, _ = prepared(private)
    with app.state.store.transaction() as db:
        db.execute("INSERT INTO control_schedulers VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ('owner-a', 1, 'synthetic-generation', 'synthetic-session', 0, '{}', 0, 'manual', 0, ''))
    assert permission(browser, auth).json() == {'authorized': False}


@pytest.mark.parametrize('state', ['QUEUED', 'CLAIMED', 'CANCEL_REQUESTED', 'NEEDS_REVIEW'])
def test_external_unfinished_publication_refuses_unlock(private, state):
    from test_installation_hold import control_job
    from storyfx_server.store import timestamp
    app, browser, _, _, auth, _, _ = prepared(private)
    with app.state.store.transaction() as db:
        identity = control_job(db, owner='owner-a', state=state)
        payload = json.loads(db.execute('SELECT publication FROM control_recipe_steps').fetchone()[0])
        payload['due_at'] = timestamp(app.state.store.clock())
        db.execute('UPDATE control_jobs SET payload=? WHERE id=?', (json.dumps(payload), identity))
    assert permission(browser, auth).json() == {'authorized': False}
