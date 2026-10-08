"""Revalidate current native bindings under the claim transaction; never reuse receipts."""
import json
import pytest
from test_private_auth import private
from test_control_android import setup, start
from storyfx_server.store import DomainError


def prepared(private):
    app, browser, _, now, auth, contact, device = setup(private)
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    assert start(browser).status_code == 200
    broker = app.state.control_scheduler.broker
    with app.state.store.transaction() as db:
        node = dict(db.execute('SELECT n.*,a.enabled FROM control_nodes n JOIN control_android_links a ON n.id=a.node_id').fetchone())
        job = dict(db.execute('SELECT * FROM control_jobs ORDER BY created,id LIMIT 1').fetchone())
    return app, browser, broker, now, auth, node, job


@pytest.mark.parametrize('sql,error', [
    ("UPDATE control_android_links SET profile='Validation technique changed'", 'ANDROID_PROFILE_BINDING_CHANGED'),
    ('UPDATE control_android_links SET enabled=0', 'ANDROID_EXECUTOR_NOT_READY'),
    ('UPDATE devices SET revoked=1', 'ANDROID_PROFILE_BINDING_CHANGED'),
    ('DELETE FROM control_android_links', 'ANDROID_PROFILE_BINDING_CHANGED'),
])
def test_claim_rechecks_after_principal_snapshot_without_touching_queue(private, sql, error):
    app, _, broker, _, _, node, job = prepared(private)
    with app.state.store.transaction() as db:
        db.execute(sql)
    with pytest.raises(DomainError, match=error):
        broker.claim(node)
    with app.state.store.transaction() as db:
        assert dict(db.execute('SELECT * FROM control_jobs WHERE id=?', (job['id'],)).fetchone()) == job


def test_ready_rechecks_binding_but_late_receipt_survives_readiness_change(private):
    app, _, broker, _, _, node, _ = prepared(private)
    job = broker.claim(node)['job']
    with app.state.store.transaction() as db:
        db.execute('UPDATE control_android_links SET enabled=0,ready=0')
    with pytest.raises(DomainError, match='ANDROID_EXECUTOR_NOT_READY'):
        broker.ready(node, job['id'])
    result = broker.complete(node, job['id'], 'NEEDS_REVIEW', 'result_uncertain')
    assert result == {'recorded': True}
    assert broker.complete(node, job['id'], 'NEEDS_REVIEW', 'result_uncertain') == result
    with pytest.raises(DomainError, match='PUBLICATION_RESULT_ALREADY_RECORDED'):
        broker.complete(node, job['id'], 'CONFIRMED', 'own_status_verified')


def test_facebook_payload_cannot_claim_ready_or_accept_whatsapp_proof(private):
    app, _, broker, _, _, node, job = prepared(private)
    payload = json.loads(job['payload']); payload['platform'] = 'Facebook'
    with app.state.store.transaction() as db:
        db.execute('UPDATE control_jobs SET payload=?', (json.dumps(payload),))
    with pytest.raises(DomainError, match='ADAPTER_NOT_VALIDATED'):
        broker.claim(node)
    with app.state.store.transaction() as db:
        db.execute("UPDATE control_jobs SET state='CLAIMED',claimed=? WHERE id=?", (app.state.store.clock(), job['id']))
    with pytest.raises(DomainError, match='ADAPTER_NOT_VALIDATED'):
        broker.ready(node, job['id'])
    with pytest.raises(DomainError, match='ANDROID_RESULT_INVALID'):
        broker.complete(node, job['id'], 'CONFIRMED', 'own_status_verified')
    with app.state.store.transaction() as db:
        assert db.execute('SELECT completed FROM control_jobs WHERE id=?', (job['id'],)).fetchone()[0] is None


def test_media_capability_change_after_node_read_cannot_authorize_final_action(private):
    app, _, broker, _, _, node, _ = prepared(private)
    node['media_modes_ready'] = True
    job = broker.claim(node)['job']
    payload = job['payload']; payload['engine'] = 'intro'
    with app.state.store.transaction() as db:
        db.execute('UPDATE control_jobs SET payload=? WHERE id=?', (json.dumps(payload), job['id']))
        db.execute('UPDATE control_android_media SET ready=0')
    with pytest.raises(DomainError, match='ANDROID_MEDIA_PERMISSION_REQUIRED'):
        broker.ready(node, job['id'])
