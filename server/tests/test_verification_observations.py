"""Counters describe observations only; they never upgrade publication evidence."""
import json
import pytest
from test_private_auth import private, login
from test_attempt_diagnostics import attempt, diagnostics
from storyfx_server.control_attempt_diagnostics import OBSERVATION_DEFAULTS


def uncertain(**observations):
    return {'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain', 'diagnostics': {
        **diagnostics(), 'verified_count': 0, 'verification_method': 'none', **observations}}


def test_observations_are_owner_private_immutable_and_not_publication_proof(private):
    app, browser, _, auth, job, path = attempt(private)
    body = uncertain(peak_verified_count=3, verification_observations=17, verification_started=True)
    assert browser.post(path, headers=auth, json=body).status_code == 200
    assert browser.post(path, headers=auth, json=body).status_code == 200
    report = next(row for row in browser.get('/v1/control').json()['reports'] if row['id'] == job['id'])
    assert report['diagnostics'] == body['diagnostics']
    assert report['state'] == 'NEEDS_REVIEW' and not report['batch_count_verified']
    # Full receipt accepted, then rollback negotiates omission and loses its response:
    # the persisted stripped receipt must still be accepted after a server upgrade.
    assert browser.post(path, headers=auth, json=uncertain()).status_code == 200
    assert browser.post(path, headers=auth, json=uncertain(**OBSERVATION_DEFAULTS)).status_code == 200
    repeated = next(row for row in browser.get('/v1/control').json()['reports'] if row['id'] == job['id'])
    assert repeated['diagnostics'] == report['diagnostics'] and repeated['completed_at'] == report['completed_at']
    with app.state.store.transaction() as db:
        # The original JSON stays byte-shape-compatible with the previous backend's compare.
        base = json.loads(db.execute('SELECT value FROM control_attempt_diagnostics WHERE job_id=?', (job['id'],)).fetchone()[0])
        assert base == {key: value for key, value in body['diagnostics'].items() if key not in OBSERVATION_DEFAULTS}
        assert db.execute('SELECT COUNT(*) FROM control_attempt_observations').fetchone()[0] == 1
    altered = uncertain(peak_verified_count=2, verification_observations=17, verification_started=True)
    assert browser.post(path, headers=auth, json=altered).status_code == 409
    assert browser.get('/health').json()['verification_observation_diagnostics'] is True
    login(browser, 'owner-b')
    assert browser.get('/v1/control').json()['reports'] == []


def test_historical_receipt_replays_with_absent_or_null_fields_without_rewrite(private):
    app, browser, _, auth, job, path = attempt(private)
    old = uncertain()
    # Insert exactly the historical structured JSON, with no extension table entry.
    with app.state.store.transaction() as db:
        db.execute('UPDATE control_jobs SET state=?,evidence=?,completed=? WHERE id=?',
                   (old['state'], old['evidence'], app.state.store.clock(), job['id']))
        raw = json.dumps(old['diagnostics'], indent=2)
        db.execute('INSERT INTO control_attempt_diagnostics VALUES (?,?,?,?)',
                   (job['id'], 'owner-a', app.state.store.clock(), raw))
    assert browser.post(path, headers=auth, json=old).status_code == 200
    assert browser.post(path, headers=auth, json=uncertain(**OBSERVATION_DEFAULTS)).status_code == 200
    report = next(row for row in browser.get('/v1/control').json()['reports'] if row['id'] == job['id'])
    assert all(report['diagnostics'][key] is None for key in OBSERVATION_DEFAULTS)
    for key, value in [('peak_verified_count', 0), ('verification_observations', 0), ('verification_started', False)]:
        assert browser.post(path, headers=auth, json=uncertain(**{key: value})).status_code == 409
    with app.state.store.transaction() as db:
        assert db.execute('SELECT value FROM control_attempt_diagnostics WHERE job_id=?', (job['id'],)).fetchone()[0] == raw
        assert db.execute('SELECT COUNT(*) FROM control_attempt_observations').fetchone()[0] == 0


@pytest.mark.parametrize('key,value', [('peak_verified_count', -1), ('peak_verified_count', 31),
    ('peak_verified_count', True), ('peak_verified_count', '1'), ('verification_observations', -1),
    ('verification_observations', 3001), ('verification_observations', True), ('verification_started', 1),
    ('verification_started', 'true')])
def test_invalid_observation_types_and_ranges_are_refused_without_receipt(private, key, value):
    app, browser, _, auth, job, path = attempt(private)
    assert browser.post(path, headers=auth, json=uncertain(**{key: value})).status_code == 422
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_attempt_observations').fetchone()[0] == 0
        assert db.execute('SELECT state FROM control_jobs WHERE id=?', (job['id'],)).fetchone()[0] == 'CLAIMED'


@pytest.mark.parametrize('peak,observations,started', [(None, 0, False), (0, 1, True), (30, 3000, True)])
def test_valid_observation_bounds_remain_diagnostic_only(private, peak, observations, started):
    _, browser, _, auth, _, path = attempt(private)
    body = uncertain(peak_verified_count=peak, verification_observations=observations, verification_started=started)
    assert browser.post(path, headers=auth, json=body).status_code == 200


def test_peak_equal_expected_cannot_replace_verified_batch(private):
    app, browser, _, auth, job, path = attempt(private)
    body = uncertain(peak_verified_count=3, verification_observations=3000, verification_started=True)
    body.update(state='CONFIRMED', evidence='own_status_verified')
    assert browser.post(path, headers=auth, json=body).status_code == 422
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_attempt_diagnostics').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM control_attempt_observations').fetchone()[0] == 0
        assert db.execute('SELECT state FROM control_jobs WHERE id=?', (job['id'],)).fetchone()[0] == 'CLAIMED'
