"""Atomic one-attempt reservations shared by manual launch and the scheduler."""
import json
from uuid import uuid4
from .store import DomainError


def supported(value):
    return (value['platform'] == 'WhatsApp' and value['engine'] == 'multi'
            and 1 <= value['count'] <= 30 and not value.get('page_name') and not value.get('page'))


def reserve(broker, user, snapshot, selected, *, strict=True, scheduler_id=None):
    accepted = []
    with broker.store.transaction() as db:
        broker.catalog.revision(db, user['id'], snapshot['revision'])
        if scheduler_id is not None:
            state = db.execute('SELECT enabled,generation FROM control_schedulers WHERE owner_id=?', (user['id'],)).fetchone()
            if not state or not state['enabled'] or state['generation'] != scheduler_id:
                return []
        for value in selected:
            if db.execute('SELECT 1 FROM control_jobs WHERE owner_id=? AND occurrence=?', (user['id'],value['id'])).fetchone():
                if strict:
                    raise DomainError('OCCURRENCE_ALREADY_REQUESTED',409)
                continue
            nodes = [node for node in snapshot['nodes'] if node['connected'] and value['device'] in node['profiles']]
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
            payload = {**row, 'due_at':value['due_at'], 'catalog_revision':snapshot['revision'],
                       'execution_origin':'web_windows_bridge', 'web_triggered':True}
            if scheduler_id is not None:
                payload['scheduler_generation'] = scheduler_id
            identity = str(uuid4())
            db.execute('INSERT INTO control_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (identity,user['id'],nodes[0]['id'],value['id'],json.dumps(payload),'QUEUED',broker.store.clock(),None,None,None))
            broker.terminal.emit(db,user['id'],'QUEUED',value['device'],value['system'])
            accepted.append({'job_id':identity,'occurrence_id':value['id'],'state':'QUEUED'})
    return accepted
