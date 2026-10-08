"""Atomic one-attempt reservations shared by manual launch and the scheduler."""
import json
from uuid import uuid4
from .store import DomainError
from .control_android import executors
from .control_media_modes import supported_media
from .control_recipe_state import active_recipe, assert_unlocked


def supported(value):
    return supported_media(value)


def reserve(broker, user, snapshot, selected, *, strict=True, scheduler_id=None):
    accepted = []
    with broker.store.transaction() as db:
        if active_recipe(db, user['id']):
            if not strict:
                return []
            assert_unlocked(db, user['id'])
        broker.catalog.revision(db, user['id'], snapshot['revision'])
        if scheduler_id is not None:
            state = db.execute('SELECT enabled,generation FROM control_schedulers WHERE owner_id=?', (user['id'],)).fetchone()
            if not state or not state['enabled'] or state['generation'] != scheduler_id:
                return []
        for value in selected:
            if not supported(value):
                if strict:
                    raise DomainError('ADAPTER_NOT_VALIDATED', 409)
                continue
            if db.execute('SELECT 1 FROM control_jobs WHERE owner_id=? AND occurrence=?', (user['id'],value['id'])).fetchone():
                if strict:
                    raise DomainError('OCCURRENCE_ALREADY_REQUESTED',409)
                continue
            nodes = executors(snapshot, value)
            if len(nodes) != 1:
                if strict:
                    raise DomainError('WINDOWS_EXECUTOR_UNAVAILABLE',409)
                continue
            node = db.execute('SELECT last_seen,revoked FROM control_nodes WHERE id=? AND owner_id=?', (nodes[0]['id'],user['id'])).fetchone()
            if not node or node['revoked'] or node['last_seen'] is None or broker.store.clock()-node['last_seen'] >= 45:
                if strict:
                    raise DomainError('WINDOWS_EXECUTOR_UNAVAILABLE',409)
                continue
            row = next(row for row in snapshot['collections']['matrix'] if row['id'] == value['row_id'])
            if not row.get('enabled', True):
                raise DomainError('PUBLICATION_PLAN_CHANGED', 409)
            payload = {**row, 'due_at':value['due_at'], 'catalog_revision':snapshot['revision'],
                       'execution_origin':'web_android_agent' if nodes[0].get('executor') == 'android_whatsapp_images_v1' else 'web_windows_bridge', 'web_triggered':True}
            if scheduler_id is not None:
                payload['scheduler_generation'] = scheduler_id
            identity = str(uuid4())
            db.execute('INSERT INTO control_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (identity,user['id'],nodes[0]['id'],value['id'],json.dumps(payload),'QUEUED',broker.store.clock(),None,None,None))
            broker.terminal.emit(db,user['id'],'QUEUED',value['device'],value['system'])
            accepted.append({'job_id':identity,'occurrence_id':value['id'],'state':'QUEUED'})
    return accepted
