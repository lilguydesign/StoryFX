"""Explicit retries preserve audits, owners, plans, readiness and uncertain-send guards."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from test_private_auth import private, login
from test_control_android import setup, start
from test_control_center import HEADERS, add, executor
from storyfx_server.control_recovery import SAFE_FAILURES


def failed(private, state='FAILED_BEFORE_PUBLICATION', evidence='updates_navigation_failed'):
    app, browser, provider, now, auth, contact, _ = setup(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    assert start(browser).status_code == 200
    jobs = []
    for _ in range(2):
        job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
        assert job
        result = browser.post('/v1/control/android/jobs/' + job['id'] + '/complete', headers=auth,
                              json={'state':state, 'evidence':evidence})
        assert result.status_code == 200
        jobs.append(job)
    return app, browser, provider, now, auth, contact, jobs[0]


def retry(browser, job, headers=HEADERS, revision=None):
    revision = browser.get('/v1/control').json()['revision'] if revision is None else revision
    return browser.post('/v1/control/jobs/' + job['id'] + '/retry', headers=headers,
                        json={'revision':revision})


def test_retry_keeps_original_history_and_never_duplicates_same_request(private):
    app, browser, _, _, auth, _, original = failed(private)
    accepted = retry(browser, original)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()['original_audit_preserved']
    assert retry(browser, original).status_code == 409
    child = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    assert child['id'] == accepted.json()['job_id']
    assert child['occurrence_id'] != original['occurrence_id']
    assert child['payload']['retry_parent'] == original['id']
    assert child['payload']['original_occurrence'] == original['occurrence_id']
    assert child['payload']['retry_depth'] == 1
    for key in ('device','platform','system','engine','album','album2','count','page','page_name','due_at'):
        assert child['payload'].get(key) == original['payload'].get(key)
    path = '/v1/control/android/jobs/' + child['id'] + '/complete'
    assert browser.post(path, headers=auth, json={'state':'CONFIRMED','evidence':'own_status_verified'}).status_code == 200
    snapshot = browser.get('/v1/control').json()
    parent = next(r for r in snapshot['reports'] if r['id'] == original['id'])
    assert parent['state'] == 'FAILED_BEFORE_PUBLICATION'
    planned = next(r for r in snapshot['schedule'] if r['id'] == original['occurrence_id'])
    assert planned['state'] == 'CONFIRMED'
    assert retry(browser, child).status_code == 409
    app.state.control_scheduler.tick()
    assert len(browser.get('/v1/control').json()['reports']) == 3


@pytest.mark.parametrize('state,evidence', [('CONFIRMED','own_status_verified'),
    ('NEEDS_REVIEW','result_uncertain'), ('FAILED_BEFORE_PUBLICATION','preflight_refused'),
    ('FAILED_BEFORE_PUBLICATION','share_selection_refused'),
    ('FAILED_BEFORE_PUBLICATION','contacts_preview_refused')])
def test_uncertain_confirmed_generic_and_picker_results_cannot_be_replayed(private, state, evidence):
    _, browser, _, _, _, _, job = failed(private, state, evidence)
    before = len(browser.get('/v1/control').json()['reports'])
    assert retry(browser, job).status_code == 409
    assert len(browser.get('/v1/control').json()['reports']) == before


def test_retry_requires_owner_csrf_current_plan_and_ready_phone(private):
    _, browser, _, _, auth, contact, job = failed(private)
    assert retry(browser, job, headers={}).status_code == 403
    assert retry(browser, job, revision=0).status_code == 409
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**contact,'screen_locked':True})
    assert retry(browser, job).status_code == 409
    login(browser, 'owner-b')
    assert retry(browser, job).status_code == 404


def test_retry_refuses_changed_media_stale_nodes_and_old_day(private):
    _, browser, _, now, auth, contact, job = failed(private)
    now[0] += 46
    assert retry(browser, job).status_code == 409
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    snapshot = browser.get('/v1/control').json()
    row = snapshot['collections']['matrix'][0]
    value = {k:v for k,v in row.items() if k != 'id'}
    value['count'] = 2
    assert browser.put('/v1/control/settings/matrix/' + row['id'], headers=HEADERS,
                       json={'revision':snapshot['revision'],'value':value}).status_code == 200
    assert retry(browser, job).status_code == 409
    now[0] += 86400
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    assert retry(browser, job).status_code == 409


def test_each_safe_failure_is_valid_but_never_a_confirmation(private):
    _, browser, _, _, auth, contact, _ = setup(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    start(browser)
    job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    path = '/v1/control/android/jobs/' + job['id'] + '/complete'
    for stage in SAFE_FAILURES:
        assert browser.post(path, headers=auth, json={'state':'CONFIRMED','evidence':stage}).status_code == 422
    assert browser.post(path, headers=auth, json={'state':'FAILED_BEFORE_PUBLICATION',
                        'evidence':'album_media_unavailable'}).status_code == 200
    assert retry(browser, job).status_code == 200


@pytest.mark.parametrize('rebind', [False, True])
@pytest.mark.parametrize('windows_ready', [False, True])
def test_retry_rechecks_binding_after_snapshot_without_consuming_parent(private, monkeypatch, rebind, windows_ready):
    app, browser, _, _, auth, contact, parent = failed(private)
    add(browser, 'profiles', name='Validation technique 2')
    windows = executor(browser) if windows_ready else None
    if windows:
        assert browser.post('/v1/control/windows/heartbeat', headers=windows,
                            json={'profiles': ['Validation technique']}).status_code == 200
    snapshot = browser.get('/v1/control').json()
    broker = app.state.control_scheduler.broker
    with app.state.store.transaction() as db:
        before = dict(db.execute('SELECT * FROM control_jobs WHERE id=?', (parent['id'],)).fetchone())
    original, captured, proceed = broker.snapshot, Event(), Event()

    def delayed(user):
        value = original(user)
        captured.set()
        assert proceed.wait(10)
        return value

    monkeypatch.setattr(broker, 'snapshot', delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(retry, browser, parent, revision=snapshot['revision'])
        try:
            assert captured.wait(10)
            if rebind:
                changed = browser.post('/v1/control/android/bind', headers=auth,
                                       json={'profile': 'Validation technique 2', 'enabled': True})
                assert changed.status_code == 200
            assert browser.post('/v1/control/android/heartbeat', headers=auth, json=contact).json()['ready']
        finally:
            proceed.set()
        response = task.result(10)
    monkeypatch.setattr(broker, 'snapshot', original)
    with app.state.store.transaction() as db:
        assert dict(db.execute('SELECT * FROM control_jobs WHERE id=?', (parent['id'],)).fetchone()) == before
    if rebind:
        assert response.status_code == 409 and response.json()['error'] == 'ANDROID_EXECUTOR_NOT_READY'
        assert len(browser.get('/v1/control').json()['reports']) == 2
        assert browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job'] is None
    else:
        assert response.status_code == 200
        child = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
        assert child['id'] == response.json()['job_id']
        assert child['occurrence_id'] != parent['occurrence_id']
        assert child['payload']['retry_parent'] == parent['id']
        assert child['payload']['device'] == parent['payload']['device']
        assert len(browser.get('/v1/control').json()['reports']) == 3
    if windows:
        assert browser.post('/v1/control/windows/claim', headers=windows, json={}).json()['job'] is None
