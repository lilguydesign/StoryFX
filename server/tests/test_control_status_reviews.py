"""Empty-own-status proof is fresh, owner-bound, pre-send only, and atomic."""
import pytest
from test_private_auth import private
from test_control_recovery import failed, retry
from test_control_center import HEADERS


def contact_empty(browser, auth, contact, **values):
    return browser.post('/v1/control/android/heartbeat', headers=auth,
                        json={**contact, 'own_status_empty': True, **values})


def batch(browser, jobs):
    return browser.post('/v1/control/retry-batch', headers=HEADERS,
                        json={'revision': browser.get('/v1/control').json()['revision'],
                              'jobs': jobs})


def test_generic_failure_requires_fresh_empty_proof_and_keeps_audit(private):
    _, browser, _, now, auth, contact, job = failed(private, evidence='preflight_refused')
    assert retry(browser, job).status_code == 409
    contact_empty(browser, auth, contact)
    reports = browser.get('/v1/control').json()['reports']
    assert next(r for r in reports if r['id'] == job['id'])['empty_status_review_available']
    now[0] += 45
    assert retry(browser, job).status_code == 409
    contact_empty(browser, auth, contact)
    accepted = retry(browser, job)
    assert accepted.status_code == 200
    child = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    assert child['payload']['retry_parent'] == job['id']
    assert child['payload']['original_occurrence'] == job['occurrence_id']
    assert retry(browser, job).status_code == 409


@pytest.mark.parametrize('values', [{'own_status_empty': False}, {'screen_locked': True},
                                   {'service_ready': False}, {'media_ready': False}])
def test_empty_proof_is_withdrawn_when_observation_or_permission_disappears(private, values):
    _, browser, _, _, auth, contact, job = failed(private, evidence='preflight_refused')
    contact_empty(browser, auth, contact)
    contact_empty(browser, auth, contact, **values)
    assert retry(browser, job).status_code == 409


@pytest.mark.parametrize('state,evidence', [('CONFIRMED', 'own_status_verified'),
    ('NEEDS_REVIEW', 'result_uncertain'), ('FAILED_BEFORE_PUBLICATION', 'share_selection_refused')])
def test_empty_proof_never_replays_confirmed_uncertain_or_picker_results(private, state, evidence):
    _, browser, _, _, auth, contact, job = failed(private, state, evidence)
    contact_empty(browser, auth, contact)
    assert retry(browser, job).status_code == 409


def test_atomic_batch_rolls_back_all_children_on_invalid_parent(private):
    _, browser, _, _, auth, contact, _ = failed(private, evidence='preflight_refused')
    contact_empty(browser, auth, contact)
    jobs = [r['id'] for r in browser.get('/v1/control').json()['reports']]
    before = len(jobs)
    assert batch(browser, [jobs[0], '00000000-0000-0000-0000-000000000001']).status_code == 404
    assert len(browser.get('/v1/control').json()['reports']) == before
    assert batch(browser, [jobs[0], jobs[0]]).status_code == 422
    result = batch(browser, jobs)
    assert result.status_code == 200 and len(result.json()['jobs']) == 2
    assert batch(browser, jobs).status_code == 409
    assert len(browser.get('/v1/control').json()['reports']) == before + 2


def test_empty_proof_cannot_cover_statuses_that_may_have_expired(private):
    _, browser, _, now, auth, contact, job = failed(private, evidence='preflight_refused')
    now[0] += 23 * 3600
    contact_empty(browser, auth, contact)
    assert retry(browser, job).status_code == 409


def test_active_provider_job_invalidates_empty_proof(private):
    _, browser, _, _, auth, contact, job = failed(private, evidence='preflight_refused')
    contact_empty(browser, auth, contact)
    assert retry(browser, job).status_code == 200
    browser.post('/v1/control/android/claim', headers=auth, json={})
    contact_empty(browser, auth, contact)
    original = next(r for r in browser.get('/v1/control').json()['reports'] if r['id'] == job['id'])
    assert not original['empty_status_review_available']


def test_empty_proof_must_follow_original_completion(private):
    app, browser, _, _, auth, contact, job = failed(private, evidence='preflight_refused')
    contact_empty(browser, auth, contact)
    with app.state.store.transaction() as db:
        db.execute('UPDATE control_status_reviews SET observed=observed-1')
    assert retry(browser, job).status_code == 409
