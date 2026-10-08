"""Canonical secondary resolution and physical exclusion; no Facebook dispatch path."""
import json
from uuid import uuid4
import pytest
from test_private_auth import private
from test_control_center import add
from android_profile_fixtures import fixture, associate
from storyfx_server.control_facebook_foundation import resolve_secondary, physical_busy, require_manual_trial, capability
from storyfx_server.store import DomainError


def associated(private):
    app, browser, provider, now, auth, contact, body = fixture(private)
    assert associate(browser, body).status_code == 200
    return app, browser, now, auth, contact, body


def target(db, body):
    return resolve_secondary(db, 'owner-a', body['profile_id'], body['device_id'])


def test_canonical_target_independent_of_wa_enabled_but_never_ready_for_facebook(private):
    app, browser, now, auth, _, body = associated(private)
    assert browser.post('/v1/control/android/bind', headers=auth,
                        json={'profile': 'Validation technique', 'enabled': False}).status_code == 200
    with app.state.store.transaction() as db:
        resolved = target(db, body)
        assert resolved.device_id == body['device_id'] and resolved.profile_id == body['profile_id']
        assert 'Validation technique' not in repr(resolved)
        assert not physical_busy(db, resolved)
        with pytest.raises(DomainError, match='ADAPTER_NOT_VALIDATED'):
            require_manual_trial(db, 'owner-a', body['profile_id'], now[0], body['device_id'])
    assert capability()['manual_trial_ready'] is False and capability()['auto_ready'] is False


def test_same_hardware_does_not_create_canonical_permission(private):
    app, browser, _, _, _, body = associated(private)
    other = next(p for p in browser.get('/v1/control').json()['collections']['profiles'] if p['name'] == 'Validation technique 3')
    with app.state.store.transaction() as db:
        with pytest.raises(DomainError, match='FACEBOOK_PROFILE_NOT_ASSOCIATED'):
            resolve_secondary(db, 'owner-a', other['id'])
        with pytest.raises(DomainError, match='FACEBOOK_PROFILE_NOT_ASSOCIATED'):
            resolve_secondary(db, 'owner-b', body['profile_id'])
        with pytest.raises(DomainError, match='FACEBOOK_DEVICE_MISMATCH'):
            resolve_secondary(db, 'owner-a', body['profile_id'], str(uuid4()))


@pytest.mark.parametrize('sql', [
    'UPDATE control_android_profiles SET revoked=1',
    "UPDATE control_android_profiles SET node_id='synthetic-other'",
    'UPDATE control_nodes SET revoked=1', 'UPDATE devices SET revoked=1',
    "UPDATE devices SET owner_id='synthetic-other'",
    "DELETE FROM control_items WHERE json_name='Validation technique'",
    "UPDATE control_items SET value='{\"enabled\":false}' WHERE json_name='Validation technique 2'",
])
def test_mutations_or_missing_primary_are_rechecked_in_same_transaction(private, sql):
    app, _, _, _, _, body = associated(private)
    with app.state.store.transaction() as db:
        target(db, body)
        db.execute(sql)
        with pytest.raises(DomainError):
            target(db, body)


def test_both_secondaries_share_one_physical_lock_without_hardware_metadata(private):
    app, browser, _, _, _, body = associated(private)
    other = next(p for p in browser.get('/v1/control').json()['collections']['profiles'] if p['name'] == 'Validation technique 3')
    assert associate(browser, dict(body, client_key=str(uuid4()), profile_id=other['id'])).status_code == 200
    with app.state.store.transaction() as db:
        db.execute("UPDATE control_items SET value=json_set(value,'$.adb_serial','') WHERE collection='profiles'")
        resolved = target(db, body)
        peer = resolve_secondary(db, 'owner-a', other['id'])
        assert peer.device_id == resolved.device_id and peer.node_id == resolved.node_id
        db.execute('INSERT INTO control_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                   ('synthetic-job', 'owner-a', peer.node_id, 'synthetic-occurrence',
                    json.dumps({'device': peer.profile}), 'NEEDS_REVIEW', 1, 2, None, None))
        assert physical_busy(db, resolved)
        assert not physical_busy(db, resolved, exclude_job_id='synthetic-job')
        db.execute("UPDATE control_jobs SET completed=3 WHERE id='synthetic-job'")
        assert not physical_busy(db, resolved)


@pytest.mark.parametrize('state', ['QUEUED', 'CLAIMED', 'CANCEL_REQUESTED', 'NEEDS_REVIEW'])
def test_windows_peer_with_same_hardware_only_excludes_never_authorizes(private, state):
    app, _, _, _, _, body = associated(private)
    with app.state.store.transaction() as db:
        resolved = target(db, body)
        db.execute('INSERT INTO control_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                   ('synthetic-job', 'owner-a', 'synthetic-windows-node', 'synthetic-occurrence',
                    json.dumps({'device': 'Validation technique 3'}), state, 1, 2, None, None))
        assert physical_busy(db, resolved)


def test_resolution_requires_a_caller_transaction(private):
    app, _, _, _, _, body = associated(private)
    import sqlite3
    db = sqlite3.connect(app.state.store.path)
    try:
        with pytest.raises(DomainError, match='NATIVE_TRANSACTION_REQUIRED'):
            resolve_secondary(db, 'owner-a', body['profile_id'])
    finally:
        db.close()


@pytest.mark.parametrize('state', ['QUEUED', 'CLAIMED', 'STARTED', 'NEEDS_REVIEW'])
def test_diagnostic_activity_on_canonical_device_is_excluded(private, state):
    app, _, now, _, _, body = associated(private)
    with app.state.store.transaction() as db:
        resolved = target(db, body)
        db.execute('''INSERT INTO jobs(id,occurrence_key,device_id,kind,status,scheduled_at,expires_at,created_at)
          VALUES (?,?,?,'diagnostic',?,?,?,?)''',
          (str(uuid4()), str(uuid4()), body['device_id'], state, now[0], now[0] + 60, now[0]))
        assert physical_busy(db, resolved)


def test_association_cannot_change_between_resolution_and_same_transaction_decision(private):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    app, _, _, _, _, body = associated(private)
    attempting, entered = Event(), Event()

    def revoke():
        attempting.set()
        with app.state.store.transaction() as writer:
            entered.set()
            writer.execute('UPDATE control_android_profiles SET revoked=1')

    with ThreadPoolExecutor(max_workers=1) as pool:
        with app.state.store.transaction() as db:
            first = target(db, body)
            future = pool.submit(revoke)
            assert attempting.wait(timeout=2)
            assert not entered.wait(timeout=.1)
            assert target(db, body) == first
        future.result(timeout=5)
    with app.state.store.transaction() as db:
        with pytest.raises(DomainError, match='FACEBOOK_PROFILE_NOT_ASSOCIATED'):
            target(db, body)
