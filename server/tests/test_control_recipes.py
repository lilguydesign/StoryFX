"""Draft isolation, persistent owner locks and unchanged pre-existing jobs."""
from uuid import uuid4
from test_private_auth import private, login
from test_control_center import HEADERS, add, executor
from test_control_android import start
from recipe_fixtures import ROOT, fixture, action, launch, current, receipt


def test_draft_is_inert_and_idempotent_even_after_catalog_change(private):
    app, browser, _, _, _, _, recipe, body = fixture(private)
    assert recipe['state'] == 'DRAFT' and not recipe['lock_held']
    assert browser.get('/v1/control').json()['reports'] == []
    assert browser.post(ROOT, headers=HEADERS, json=body).json()['id'] == recipe['id']
    altered = {**body, 'row_ids': list(reversed(body['row_ids']))}
    assert browser.post(ROOT, headers=HEADERS, json=altered).status_code == 409
    add(browser, 'albums', name='Validation technique changement')
    assert browser.post(ROOT, headers=HEADERS, json=body).json()['id'] == recipe['id']
    assert action(browser, recipe, 'start').status_code == 409
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_recipe_locks').fetchone()[0] == 0


def test_owner_origin_closed_schema_and_facebook_are_enforced(private):
    _, browser, _, _, _, _, recipe, body = fixture(private)
    assert browser.post(ROOT, json=body).status_code == 403
    assert browser.post(ROOT, headers=HEADERS, json={**body, 'executor': 'windows'}).status_code == 422
    assert browser.post(ROOT, headers=HEADERS, json={**body, 'row_ids': [body['row_ids'][0]] * 2}).status_code == 422
    assert browser.post(ROOT, headers=HEADERS, json={**body, 'recipient': 'synthetic-private-marker'}).status_code == 422
    changed = add(browser, 'matrix', name='Validation technique Facebook', device='Validation technique',
                  platform='Facebook', system='Validation technique', engine='multi', album2='Validation technique', count=3,
                  page='CM', page_name='Validation technique page')
    facebook = next(row for row in changed['collections']['matrix'] if row['platform'] == 'Facebook')
    denied = browser.post(ROOT, headers=HEADERS, json={**body, 'client_key': str(uuid4()),
                         'revision': changed['revision'], 'row_ids': [facebook['id']]})
    assert denied.json()['error'] == 'ADAPTER_NOT_VALIDATED'
    login(browser, 'owner-b')
    assert browser.get(ROOT).json()['recipes'] == []
    assert browser.get(ROOT + '/' + recipe['id']).status_code == 404
    assert action(browser, recipe, 'start').status_code == 404


def test_start_drains_existing_jobs_and_blocks_new_reservations_without_cancelling(private):
    app, browser, _, now, auth, contact, recipe, body = fixture(private, count=1)
    assert start(browser).status_code == 200
    snapshot = browser.get('/v1/control').json()
    before = {r['id']: r['state'] for r in snapshot['reports']}
    assert set(before.values()) == {'QUEUED'}
    locked = action(browser, recipe, 'start').json()
    assert locked['state'] == 'DRAINING' and locked['external_pending'] == 2
    assert locked['scheduler_before']['enabled']
    assert browser.get('/v1/control').json()['scheduler']['enabled']
    assert action(browser, recipe, 'start').json()['id'] == recipe['id']
    assert launch(browser, recipe).json()['error'] == 'RECIPE_DRAINING'
    assert start(browser).json()['error'] == 'MANUAL_RECIPE_ACTIVE'
    assert browser.post('/v1/control/launch', headers=HEADERS, json={
        'revision': body['revision'], 'occurrence_id': snapshot['schedule'][0]['id']}).json()['error'] == 'MANUAL_RECIPE_ACTIVE'
    assert browser.post('/v1/control/catchup/launch', headers=HEADERS, json={
        'revision': body['revision'], 'profiles': ['Validation technique'], 'platforms': ['WhatsApp'],
        'start_time': '00:00'}).json()['error'] == 'MANUAL_RECIPE_ACTIVE'
    app.state.control_scheduler.tick()
    assert {r['id']: r['state'] for r in browser.get('/v1/control').json()['reports']} == before
    receipt(browser, auth)
    assert current(browser, recipe)['state'] == 'DRAINING'
    receipt(browser, auth)
    assert current(browser, recipe)['state'] == 'COOLDOWN'
    assert browser.get('/v1/control').json()['scheduler']['enabled']
    now[0] += 300
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    assert launch(browser, recipe).status_code == 200


def test_cancel_keeps_inflight_and_release_waits_for_original_receipt(private):
    app, browser, _, now, auth, _, recipe, _ = fixture(private, count=1)
    action(browser, recipe, 'start')
    accepted = launch(browser, recipe).json()
    job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    assert action(browser, recipe, 'cancel').json()['state'] == 'CANCELLED'
    assert action(browser, recipe, 'release').json()['error'] == 'RECIPE_DRAINING'
    path = '/v1/control/android/jobs/' + job['id']
    assert browser.post(path + '/ready', headers=auth, json={}).status_code == 200
    now[0] += 901
    browser.get('/v1/control')
    assert action(browser, recipe, 'release').json()['error'] == 'RECIPE_DRAINING'
    assert browser.post(path + '/complete', headers=auth, json={
        'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain'}).status_code == 200
    released = action(browser, recipe, 'release').json()
    assert released['state'] == 'RELEASED' and not released['lock_held']
    assert launch(browser, recipe).json()['job_id'] == accepted['job_id']
    assert start(browser).json()['error'] == 'RECIPE_VALIDATION_REQUIRED'


def test_lock_prevents_auth_or_revision_pause_from_cancelling_preexisting_queue(private):
    app, browser, provider, _, _, _, recipe, _ = fixture(private, count=1)
    start(browser)
    action(browser, recipe, 'start')
    add(browser, 'albums', name='Validation technique modification')
    provider.denied.add('owner-a')
    app.state.control_scheduler.tick()
    with app.state.store.transaction() as db:
        assert {row[0] for row in db.execute('SELECT state FROM control_jobs')} == {'QUEUED'}
        assert db.execute('SELECT enabled FROM control_schedulers').fetchone()[0] == 1
        original = dict(db.execute('SELECT * FROM control_schedulers').fetchone())
    app.state.control_scheduler.pause(original, 'OWNER_ACCESS_REQUIRED')
    with app.state.store.transaction() as db:
        assert {row[0] for row in db.execute('SELECT state FROM control_jobs')} == {'QUEUED'}
        assert db.execute('SELECT enabled FROM control_schedulers').fetchone()[0] == 1


def test_native_only_does_not_fall_back_to_connected_windows(private):
    _, browser, _, _, auth, contact, recipe, _ = fixture(private, count=1)
    windows = executor(browser)
    browser.post('/v1/control/windows/heartbeat', headers=windows, json={'profiles': ['Validation technique']})
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact, 'service_ready': False})
    action(browser, recipe, 'start')
    assert launch(browser, recipe).json()['error'] == 'ANDROID_EXECUTOR_NOT_READY'
    assert browser.get('/v1/control').json()['reports'] == []


def test_concurrent_create_returns_existing_plan_before_rechecking_revision(private, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread
    from storyfx_server.control_models import Change
    from storyfx_server.control_recipe_routes import RecipeDraft
    app, _, _, _, _, _, _, body = fixture(private, count=1)
    broker = app.state.control_scheduler.broker
    request = RecipeDraft(**{**body, 'client_key': str(uuid4())})
    owner = {'id': 'owner-a'}
    captured, resume = Event(), Event()
    original_read = broker.catalog.read

    def delayed_read(user):
        snapshot = original_read(user)
        if current_thread().name.startswith('recipe-race'):
            captured.set()
            assert resume.wait(10), 'Synthetic interleaving was not released'
        return snapshot

    monkeypatch.setattr(broker.catalog, 'read', delayed_read)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='recipe-race') as pool:
        pending = pool.submit(broker.recipes.create, owner, request)
        try:
            assert captured.wait(10), 'Synthetic first request did not read its catalog'
            created = broker.recipes.create(owner, request)
            broker.catalog.write(owner, 'albums', Change(revision=request.revision,
                value={'name': 'Validation technique concurrence'}))
        finally:
            resume.set()
        resumed = pending.result(timeout=10)
    assert resumed['id'] == created['id'] and resumed['revision'] == request.revision
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_recipes WHERE owner_id=? AND client_key=?',
                          (owner['id'], str(request.client_key))).fetchone()[0] == 1
