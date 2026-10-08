"""The maintenance signal is read-only, closed, aggregate and evidence-based."""
import json
import sqlite3
from test_private_auth import private
from storyfx_server.publication_observation import read_snapshot
from storyfx_server.control_recipe_observation import manual_validation
from recipe_fixtures import fixture, action, launch, receipt


def observe(app, now):
    config = {'owner_id': 'owner-a', 'device_profiles': ['Validation technique'],
              'schedule_profiles': ['Validation technique'], 'whatsapp_forbidden_profiles': [],
              'start_unix': now - 86400, 'end_unix': now + 86400}
    return read_snapshot(app.state.store.path, config, now)['manual_validation']


def test_aggregate_proves_cooldown_without_private_identifiers(private):
    app, browser, _, now, auth, contact, recipe, _ = fixture(private)
    before = observe(app, now[0])
    assert before['state'] == 'draft' and before['contract_version'] == 1 and not before['started']
    assert not before['lock_held'] and before['total_steps'] == 2
    action(browser, recipe, 'start')
    launch(browser, recipe)
    receipt(browser, auth)
    value = observe(app, now[0])
    assert value['state'] == 'cooldown' and value['lock_held'] and value['started']
    assert value['verified_steps'] == 1 and not value['automation_ready']
    assert value['interval_violation_steps'] == 0
    text = json.dumps(value)
    assert 'Validation technique' not in text and recipe['id'] not in text and 'owner-a' not in text
    now[0] += 300
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    launch(browser, recipe, 1)
    receipt(browser, auth)
    action(browser, recipe, 'release')
    value = observe(app, now[0])
    assert value['state'] == 'released' and value['verified_steps'] == 2 and value['automation_ready']
    assert value['resume_not_before'] and not value['scheduler_enabled']
    assert value['interval_violation_steps'] == 0


def test_missing_contract_is_unknown_not_a_healthy_empty_state():
    with sqlite3.connect(':memory:') as db:
        assert manual_validation(db, 'synthetic-owner', 0, set()) is None


def test_hold_excludes_only_planned_occurrences_during_its_recorded_interval(private):
    app, browser, _, now, _, _, recipe, body = fixture(private, count=1)
    from test_recipe_resume import restart
    now[0] -= 7200
    assert restart(browser, body['revision']).status_code == 200
    action(browser, recipe, 'start')
    now[0] += 7200
    config = {'owner_id': 'owner-a', 'device_profiles': ['Validation technique'],
              'schedule_profiles': ['Validation technique'], 'whatsapp_forbidden_profiles': [],
              'start_unix': now[0] - 12 * 3600, 'end_unix': now[0] + 3600}
    rows = read_snapshot(app.state.store.path, config, now[0])['rows']
    assert [row['verdict'] for row in rows] == ['late', 'manual_recipe_hold']
    action(browser, recipe, 'cancel')
    action(browser, recipe, 'release')
    assert [row['verdict'] for row in read_snapshot(app.state.store.path, config, now[0])['rows']] == ['late', 'manual_recipe_hold']
