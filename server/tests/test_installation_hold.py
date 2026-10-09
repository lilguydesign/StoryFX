"""Isolated durable replacement exclusion, including writers without the new API code."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
import sqlite3
import threading
from uuid import uuid4
import pytest
from conftest import enroll, schedule
from storyfx_server.installation_hold import acquire, release, status
from storyfx_server.installation_operator import main
from storyfx_server.store import DomainError, Store

KEY = 'a' * 64
PROOF = 'b' * 64


def context(lab):
    client, now, app = lab
    device, _ = enroll(client)
    return client, now, app.state.store, device


def hold(store, device, key=KEY):
    return acquire(store, 'validation_owner', [device], key)


def control_job(db, owner='validation_owner', state='QUEUED', completed=None):
    identity = str(uuid4())
    db.execute('INSERT INTO control_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
               (identity, owner, None, uuid4().hex, '{}', state, 1, None, completed, None))
    return identity


def test_api_enqueue_refused_without_changing_calendar_or_jobs(lab):
    client, now, store, device = context(lab)
    with store.transaction() as db:
        before = list(db.execute('SELECT * FROM control_schedulers'))
    assert hold(store, device) == {'held': True, 'created': True, 'automatic_expiry': False}
    response = schedule(client, device, now[0])
    assert response.status_code == 409
    assert response.json()['error'] == 'ANDROID_INSTALLATION_HOLD'
    with store.transaction() as db:
        assert not list(db.execute('SELECT * FROM jobs'))
        assert list(db.execute('SELECT * FROM control_schedulers')) == before


def test_hold_survives_store_restart_and_time_and_requires_exact_release(lab):
    _, now, store, device = context(lab)
    hold(store, device)
    now[0] += 86400 * 100
    restarted = Store(store.path, clock=store.clock)
    assert status(restarted, 'validation_owner', KEY)['held'] is True
    with pytest.raises(DomainError, match='INSTALLATION_HOLD_NOT_FOUND'):
        release(restarted, 'validation_owner', 'c' * 64, PROOF)
    with pytest.raises(DomainError, match='INSTALLATION_VERIFICATION_REQUIRED'):
        release(restarted, 'validation_owner', KEY, '')
    assert release(restarted, 'validation_owner', KEY, PROOF)['released']
    assert release(restarted, 'validation_owner', KEY, PROOF)['released']
    with pytest.raises(DomainError, match='INSTALLATION_RELEASE_ALREADY_RECORDED'):
        release(restarted, 'validation_owner', KEY, 'c' * 64)
    with pytest.raises(DomainError, match='INSTALLATION_OPERATION_ALREADY_USED'):
        hold(restarted, device)


@pytest.mark.parametrize('state,completed', [('QUEUED', None), ('CLAIMED', None),
    ('CANCEL_REQUESTED', None), ('NEEDS_REVIEW', None)])
def test_active_publication_blocks_acquisition(lab, state, completed):
    _, _, store, device = context(lab)
    with store.transaction() as db:
        control_job(db, state=state, completed=completed)
    with pytest.raises(DomainError, match='PUBLICATION_IN_PROGRESS'):
        hold(store, device)


def test_completed_uncertain_result_is_preserved_and_never_requeued(lab):
    _, _, store, device = context(lab)
    with store.transaction() as db:
        job = control_job(db, state='NEEDS_REVIEW', completed=5)
        before = tuple(db.execute('SELECT * FROM control_jobs WHERE id=?', (job,)).fetchone())
    hold(store, device)
    with pytest.raises(DomainError, match='ANDROID_INSTALLATION_HOLD'):
        with store.transaction() as db:
            db.execute("UPDATE control_jobs SET state='QUEUED' WHERE id=?", (job,))
    with store.transaction() as db:
        assert tuple(db.execute('SELECT * FROM control_jobs WHERE id=?', (job,)).fetchone()) == before


def test_old_process_inserts_blocked_but_other_owner_and_heartbeats_allowed(lab):
    _, now, store, device = context(lab)
    hold(store, device)
    with sqlite3.connect(store.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match='ANDROID_INSTALLATION_HOLD'):
            control_job(db)
        control_job(db, owner='another-synthetic-owner')
        db.execute('UPDATE devices SET last_seen=? WHERE id=?', (now[0], device))
    assert hold(store, device)['created'] is False
    with pytest.raises(DomainError, match='INSTALLATION_ALREADY_HELD'):
        hold(store, device, 'c' * 64)
    with pytest.raises(DomainError, match='DEVICE_NOT_FOUND_OR_REVOKED'):
        acquire(store, 'another-synthetic-owner', [device], 'c' * 64)


def test_queue_commit_wins_race_and_acquisition_refuses(lab):
    _, _, store, device = context(lab)
    written, allow_commit, entering = threading.Event(), threading.Event(), threading.Event()

    def writer():
        with store.transaction() as db:
            control_job(db)
            written.set()
            assert allow_commit.wait(5)

    def installer():
        assert written.wait(5)
        entering.set()
        with pytest.raises(DomainError, match='PUBLICATION_IN_PROGRESS'):
            hold(store, device)

    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(writer)
        second = pool.submit(installer)
        assert entering.wait(5)
        allow_commit.set()
        first.result(10)
        second.result(10)
    with store.transaction() as db:
        assert db.execute('SELECT count(*) FROM android_installation_holds').fetchone()[0] == 0


@pytest.mark.parametrize('state', ['QUEUED', 'CLAIMED', 'STARTED', 'NEEDS_REVIEW'])
def test_diagnostic_activity_blocks_acquisition(lab, state):
    client, now, store, device = context(lab)
    assert schedule(client, device, now[0]).status_code == 200
    with store.transaction() as db:
        db.execute('UPDATE jobs SET status=?', (state,))
    with pytest.raises(DomainError, match='DEVICE_ACTIVITY_IN_PROGRESS'):
        hold(store, device)


def test_released_hold_restores_normal_enqueue(lab):
    client, now, store, device = context(lab)
    hold(store, device)
    release(store, 'validation_owner', KEY, PROOF)
    assert schedule(client, device, now[0]).status_code == 200


def test_operator_closes_output_and_refuses_new_database(lab, tmp_path):
    _, _, store, device = context(lab)
    output = io.StringIO()
    request = {'action': 'acquire', 'owner_id': 'validation_owner', 'device_ids': [device], 'operation_key': KEY}
    main(store.path, io.StringIO(json.dumps(request)), output)
    assert json.loads(output.getvalue())['held']
    assert all(value not in output.getvalue() for value in (device, KEY, 'validation_owner'))
    path = tmp_path / 'missing.db'
    with pytest.raises(FileNotFoundError):
        main(path, io.StringIO(json.dumps(request)), io.StringIO())
    assert not path.exists()


def test_unrelated_integrity_errors_are_not_hidden(lab):
    _, _, store, device = context(lab)
    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction() as db:
            db.execute('INSERT INTO devices(id) VALUES (?)', (device,))


def test_idempotence_cannot_change_target_scope(lab):
    client, _, store, device = context(lab)
    second, _ = enroll(client)
    hold(store, device)
    with pytest.raises(DomainError, match='INSTALLATION_OPERATION_ALREADY_USED'):
        acquire(store, 'validation_owner', [second], KEY)


def test_scheduler_pause_is_required_and_preserved(lab):
    _, _, store, device = context(lab)
    with store.transaction() as db:
        db.execute('INSERT INTO control_schedulers VALUES (?,?,?,?,?,?,?,?,?,?)',
                   ('validation_owner', 1, 'synthetic', 'synthetic', 0, '{}', 1, 'auto', 1, ''))
    with pytest.raises(DomainError, match='WINDOWS_USB_PAUSE_REQUIRED'):
        hold(store, device)
    with store.transaction() as db:
        assert db.execute('SELECT enabled FROM control_schedulers').fetchone()[0] == 1


def test_manual_recipe_blocks_hold(lab):
    _, _, store, device = context(lab)
    with store.transaction() as db:
        db.execute('INSERT INTO control_recipe_locks VALUES (?,?)', ('validation_owner', 'synthetic-recipe'))
    with pytest.raises(DomainError, match='MANUAL_RECIPE_ACTIVE'):
        hold(store, device)


def test_old_diagnostic_writer_cannot_dispatch_terminal_row(lab):
    client, now, store, device = context(lab)
    assert schedule(client, device, now[0]).status_code == 200
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='DIAGNOSTIC_CONFIRMED'")
    hold(store, device)
    with sqlite3.connect(store.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match='ANDROID_INSTALLATION_HOLD'):
            db.execute("UPDATE jobs SET status='CLAIMED'")
