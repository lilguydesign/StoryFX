"""Synthetic receipts: closed telemetry, immutable audit and explicit proof limits."""
import pytest
from test_private_auth import private, login
from test_control_android import setup, start
from test_control_center import HEADERS


def diagnostics():
    return dict(stage='own_status_verification', app_version='0.4.14',
                expected_count=3, selected_count=3, verified_count=3, elapsed_ms=12000,
                service_ready=True, network='wifi', provider_package='whatsapp_business',
                account_verified=False, verification_method='recent_rows',
                navigation_state='own_list', own_label_count=1)


def attempt(private):
    app, browser, _, now, auth, contact, _ = setup(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    start(browser)
    job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    return app, browser, now, auth, job, '/v1/control/android/jobs/' + job['id'] + '/complete'


def test_quantified_receipt_and_no_claim_of_independent_account_or_autonomy(private):
    app, browser, _, auth, job, path = attempt(private)
    body = {'state': 'CONFIRMED', 'evidence': 'own_status_verified', 'diagnostics': diagnostics()}
    assert browser.post(path, headers=auth, json=body).status_code == 200
    assert browser.post(path, headers=auth, json=body).status_code == 200
    snapshot = browser.get('/v1/control').json()
    report = next(row for row in snapshot['reports'] if row['id'] == job['id'])
    assert report['diagnostics'] == body['diagnostics']
    assert report['expected_media_count'] == 3 and report['batch_count_verified']
    assert report['scheduled_at'] == job['payload']['due_at']
    assert report['timezone'] == 'Africa/Douala'
    assert report['attempt_id'] == job['id'] and report['parent_attempt_id'] is None
    assert not report['account_verified'] and not snapshot['total_autonomy_verified']
    assert not snapshot['autonomous_android_publication']
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_attempt_diagnostics').fetchone()[0] == 1
    app.state.control_scheduler.tick()
    assert len(browser.get('/v1/control').json()['reports']) == 2


@pytest.mark.parametrize('field,value', [('expected_count', 2), ('selected_count', 2),
    ('verified_count', None), ('verification_method', 'none'), ('provider_package', 'unknown')])
def test_incomplete_or_inconsistent_confirmation_is_refused_atomically(private, field, value):
    app, browser, _, auth, job, path = attempt(private)
    body = {'state': 'CONFIRMED', 'evidence': 'own_status_verified',
            'diagnostics': {**diagnostics(), field: value}}
    assert browser.post(path, headers=auth, json=body).status_code == 422
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_attempt_diagnostics').fetchone()[0] == 0
        assert db.execute('SELECT state FROM control_jobs WHERE id=?', (job['id'],)).fetchone()[0] == 'CLAIMED'


@pytest.mark.parametrize('field,value', [('message', 'synthetic-private-marker'),
    ('network', 'synthetic-private-marker'), ('expected_count', True),
    ('app_version', 'synthetic-private-marker'), ('elapsed_ms', 900001)])
def test_telemetry_rejects_unknown_private_content_and_invalid_types(private, field, value):
    _, browser, _, auth, _, path = attempt(private)
    response = browser.post(path, headers=auth, json={
        'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain',
        'diagnostics': {**diagnostics(), field: value}})
    assert response.status_code == 422
    assert 'synthetic-private-marker' not in response.text


def test_uncertain_result_is_immutable_but_crash_timeout_accepts_original_late_receipt(private):
    _, browser, now, auth, job, path = attempt(private)
    now[0] += 901
    snapshot = browser.get('/v1/control').json()
    assert next(row for row in snapshot['reports'] if row['id'] == job['id'])['state'] == 'NEEDS_REVIEW'
    original = {'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain',
                'diagnostics': {**diagnostics(), 'verified_count': None, 'verification_method': 'none'}}
    assert browser.post(path, headers=auth, json=original).status_code == 200
    completed = next(row for row in browser.get('/v1/control').json()['reports'] if row['id'] == job['id'])['completed_at']
    now[0] += 1
    assert browser.post(path, headers=auth, json=original).status_code == 200
    assert next(row for row in browser.get('/v1/control').json()['reports'] if row['id'] == job['id'])['completed_at'] == completed
    altered = {**original, 'diagnostics': {**original['diagnostics'], 'elapsed_ms': 13000}}
    assert browser.post(path, headers=auth, json=altered).status_code == 409
    assert browser.post(path, headers=auth, json={
        'state': 'CONFIRMED', 'evidence': 'own_status_verified', 'diagnostics': diagnostics()}).status_code == 409
    assert browser.post('/v1/control/jobs/' + job['id'] + '/retry', headers=HEADERS,
        json={'revision': snapshot['revision']}).status_code == 409


def test_old_agent_confirmation_keeps_unknown_counts_and_cannot_be_retrofitted(private):
    _, browser, _, auth, job, path = attempt(private)
    original = {'state': 'CONFIRMED', 'evidence': 'own_status_verified'}
    assert browser.post(path, headers=auth, json=original).status_code == 200
    report = next(row for row in browser.get('/v1/control').json()['reports'] if row['id'] == job['id'])
    assert report['diagnostics'] is None and not report['batch_count_verified']
    assert browser.post(path, headers=auth, json={**original, 'diagnostics': diagnostics()}).status_code == 409
    login(browser, 'owner-b')
    assert browser.get('/v1/control').json()['reports'] == []


def test_offline_confirmation_after_server_timeout_flushes_before_heartbeat(private):
    _, browser, now, auth, job, path = attempt(private)
    now[0] += 901
    timed_out = next(row for row in browser.get('/v1/control').json()['reports'] if row['id'] == job['id'])
    assert timed_out['state'] == 'NEEDS_REVIEW' and timed_out['completed_at'] is None
    # The receipt is sent first after reconnecting, while this node's heartbeat is stale.
    receipt = {'state': 'CONFIRMED', 'evidence': 'own_status_verified', 'diagnostics': diagnostics()}
    assert browser.post(path, headers=auth, json=receipt).status_code == 200
    assert browser.post(path, headers=auth, json=receipt).status_code == 200
    received = next(row for row in browser.get('/v1/control').json()['reports'] if row['id'] == job['id'])
    assert received['state'] == 'CONFIRMED' and received['batch_count_verified']
    contact = {'service_ready': True, 'media_ready': True, 'screen_locked': False, 'app_version': '0.4.14'}
    assert browser.post('/v1/control/android/heartbeat', headers=auth, json=contact).status_code == 200
    next_job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    assert next_job and next_job['id'] != job['id']


def test_health_describes_capabilities_and_never_certifies_publication(private):
    _, browser, _, _ = private
    value = browser.get('/health').json()
    assert value['publication_flags_describe'] == 'adapter_capability_only'
    assert value['native_platforms_supported'] == ['WhatsApp']
    assert value['structured_attempt_diagnostics']
    assert not value['total_autonomy_verified'] and not value['publication_verified_by_health']
