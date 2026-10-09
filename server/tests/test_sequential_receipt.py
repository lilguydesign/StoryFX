"""Synthetic API receipts: immutable separated proofs and conservative uncertain results."""
import json
from copy import deepcopy
from test_private_auth import private
from test_attempt_diagnostics import attempt, diagnostics as base_diagnostics
from test_sequential_proof import diagnostics, METHOD
from storyfx_server.control_recipe_proof import verified_receipt


def manual_attempt(private):
    app, browser, now, auth, job, path = attempt(private)
    payload = {**job['payload'], 'count': 11, 'engine': 'multi', 'recipe_id': 'synthetic'}
    with app.state.store.transaction() as db:
        db.execute('UPDATE control_jobs SET payload=? WHERE id=?', (json.dumps(payload), job['id']))
    return browser, auth, job, path, payload


def complete_diagnostics():
    return {**base_diagnostics(), **diagnostics(), 'peak_verified_count': 9,
            'verification_started': True, 'verification_observations': 10}


def test_separated_receipt_persists_idempotently_without_retrofitting(private):
    browser, auth, job, path, payload = manual_attempt(private)
    body = dict(state='CONFIRMED', evidence='own_status_verified', diagnostics=complete_diagnostics())
    assert browser.post(path, headers=auth, json=body).status_code == 200
    assert browser.post(path, headers=auth, json=body).status_code == 200
    report = next(r for r in browser.get('/v1/control').json()['reports'] if r['id'] == job['id'])
    assert report['batch_count_verified'] and not report['account_verified']
    assert report['diagnostics']['sequential_proof'] == body['diagnostics']['sequential_proof']
    assert verified_receipt({'state': 'CONFIRMED', 'evidence': 'own_status_verified', 'completed': 1},
                            report['diagnostics'], payload)
    changed = deepcopy(body)
    changed['diagnostics']['sequential_proof']['verified_elapsed_ms'][1] += 1
    assert browser.post(path, headers=auth, json=changed).status_code == 409
    omitted = deepcopy(body)
    omitted['diagnostics'].pop('sequential_proof')
    omitted['diagnostics']['verification_method'] = 'recent_visible'
    assert browser.post(path, headers=auth, json=omitted).status_code == 409


def test_partial_slice_receipt_is_uncertain_and_cannot_be_promoted(private):
    browser, auth, job, path, _ = manual_attempt(private)
    d = complete_diagnostics()
    d.update(verified_count=9, verification_method='none')
    d['sequential_proof'].update(verified_counts=[9], verified_elapsed_ms=[20000])
    body = dict(state='NEEDS_REVIEW', evidence='result_uncertain', diagnostics=d)
    assert browser.post(path, headers=auth, json=body).status_code == 200
    assert browser.post(path, headers=auth, json=body).status_code == 200
    report = next(r for r in browser.get('/v1/control').json()['reports'] if r['id'] == job['id'])
    assert not report['batch_count_verified']
    assert browser.post(path, headers=auth, json=dict(state='CONFIRMED', evidence='own_status_verified',
        diagnostics=complete_diagnostics())).status_code == 409
