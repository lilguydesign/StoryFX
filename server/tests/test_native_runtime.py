"""Synthetic physical readiness never grants a provider capability or new permission."""
import json
import pytest
from test_private_auth import private
from test_control_android import setup, start

PATH = '/v1/control/android/'


def runtime(**overrides):
    return dict(contract_version=1, global_enabled=True, service_ready=True,
                accessibility_enabled=True, screen_unlocked=True, media_permission=True, **overrides)


def settings(browser, auth):
    return browser.post(PATH + 'settings', headers=auth, json={}).json()


def test_physical_ready_with_whatsapp_off_cannot_enable_either_provider(private):
    app, browser, _, _, auth, contact, device = setup(private)
    assert browser.post(PATH + 'bind', headers=auth,
                        json={'profile': 'Validation technique', 'enabled': False}).status_code == 200
    body = {**contact, 'app_version': '0.4.16', 'native_runtime': runtime()}
    response = browser.post(PATH + 'heartbeat', headers=auth, json=body)
    assert response.json() == {'ready': False, 'reason': 'DISABLED'}
    data = settings(browser, auth)
    assert data['native_runtime'] == {'contract_version': 1, 'reported': True, 'physical_ready': True,
                                       'reason': '', 'publication_authorized': False}
    assert not data['binding']['enabled']
    assert data['capabilities']['facebook']['manual_trial_ready'] is False
    assert data['capabilities']['facebook']['auto_ready'] is False
    assert data['capabilities']['facebook']['proof_contract'] is None
    assert browser.post(PATH + 'claim', headers=auth, json={}).status_code == 409
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_jobs').fetchone()[0] == 0
        assert db.execute('SELECT ready FROM control_android_media WHERE device_id=?', (device,)).fetchone()[0] == 0


def test_global_stop_wins_even_when_whatsapp_binding_is_enabled(private):
    _, browser, _, _, auth, contact, _ = setup(private)
    value = runtime(); value['global_enabled'] = False
    response = browser.post(PATH + 'heartbeat', headers=auth, json={**contact, 'native_runtime': value})
    assert response.json() == {'ready': False, 'reason': 'GLOBAL_AGENT_DISABLED'}
    data = settings(browser, auth)
    assert data['binding']['enabled'] == 1
    assert data['native_runtime']['reason'] == 'GLOBAL_AGENT_DISABLED'
    assert browser.post(PATH + 'claim', headers=auth, json={}).status_code == 409


def test_old_heartbeat_is_compatible_and_invalidates_old_runtime_assertion(private):
    _, browser, _, _, auth, contact, _ = setup(private)
    assert settings(browser, auth)['native_runtime']['reason'] == 'NATIVE_RUNTIME_UNREPORTED'
    assert browser.post(PATH + 'heartbeat', headers=auth, json={**contact, 'native_runtime': runtime()}).json()['ready']
    assert settings(browser, auth)['native_runtime']['physical_ready']
    assert browser.post(PATH + 'heartbeat', headers=auth, json=contact).json()['ready']
    assert settings(browser, auth)['native_runtime']['reason'] == 'NATIVE_RUNTIME_UNREPORTED'
    assert start(browser).status_code == 200
    assert browser.post(PATH + 'claim', headers=auth, json={}).json()['job'] is not None


@pytest.mark.parametrize('field,value', [('contract_version', True), ('contract_version', 2),
    ('global_enabled', 1), ('service_ready', 'true'), ('accessibility_enabled', None),
    ('screen_unlocked', 'false'), ('media_permission', 0), ('provider', 'Facebook')])
def test_runtime_schema_is_strict_and_does_not_persist_rejected_input(private, field, value):
    app, browser, _, _, auth, contact, _ = setup(private)
    body = runtime(); body[field] = value
    assert browser.post(PATH + 'heartbeat', headers=auth, json={**contact, 'native_runtime': body}).status_code == 422
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_native_runtime').fetchone()[0] == 0


@pytest.mark.parametrize('field', ['service_ready', 'screen_unlocked', 'media_permission', 'accessibility_enabled'])
def test_incoherent_runtime_refused_before_heartbeat_mutation(private, field):
    app, browser, _, _, auth, contact, _ = setup(private)
    body = runtime(); body[field] = False
    with app.state.store.transaction() as db:
        before = tuple(db.execute('SELECT ready,reason FROM control_android_links').fetchone())
    response = browser.post(PATH + 'heartbeat', headers=auth, json={**contact, 'native_runtime': body})
    assert response.status_code == 422 and response.json()['error'] == 'NATIVE_RUNTIME_INCOHERENT'
    with app.state.store.transaction() as db:
        assert tuple(db.execute('SELECT ready,reason FROM control_android_links').fetchone()) == before


def test_runtime_expires_and_cannot_follow_changed_owner_session_or_node(private):
    app, browser, _, now, auth, contact, device = setup(private)
    browser.post(PATH + 'heartbeat', headers=auth, json={**contact, 'native_runtime': runtime()})
    now[0] += 45
    assert settings(browser, auth)['native_runtime']['reason'] == 'NATIVE_RUNTIME_STALE'
    now[0] -= 45
    with app.state.store.transaction() as db:
        original = dict(db.execute('SELECT * FROM control_native_runtime').fetchone())
    for column in ('owner_id', 'node_id', 'auth_session_hash', 'app_version'):
        with app.state.store.transaction() as db:
            db.execute('UPDATE control_native_runtime SET ' + column + '=?', ('synthetic-other',))
        assert settings(browser, auth)['native_runtime']['reason'] == 'NATIVE_RUNTIME_UNREPORTED'
        with app.state.store.transaction() as db:
            db.execute('UPDATE control_native_runtime SET ' + column + '=?', (original[column],))


def test_unknown_or_null_runtime_never_fabricates_a_physical_report(private):
    _, browser, _, _, auth, contact, _ = setup(private)
    response = browser.post(PATH + 'heartbeat', headers=auth, json={**contact, 'native_runtime': None})
    assert response.status_code == 200
    data = settings(browser, auth)
    assert not data['native_runtime']['reported'] and not data['native_runtime']['physical_ready']
    assert browser.get('/health').json()['native_platforms_supported'] == ['WhatsApp']
    assert browser.get('/health').json()['facebook_proof_contract'] is None
