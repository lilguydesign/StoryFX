"""Read-only permission to wake the exact bound phone for an existing due plan."""
from datetime import datetime
import json
from .control_publications import supported


def unlock_authorized(native, identity):
    user = native.principal(identity)
    node = native.node(identity, require_ready=False)
    if not node['enabled'] or node['reason'] != 'SCREEN_LOCKED':
        return {'authorized': False}
    snapshot = native.broker.snapshot(user)
    with native.store.transaction() as db:
        scheduler = db.execute('SELECT * FROM control_schedulers WHERE owner_id=?', (user['id'],)).fetchone()
        link = db.execute('SELECT profile FROM control_android_links WHERE device_id=? AND owner_id=?',
                          (identity.id, user['id'])).fetchone()
        device = db.execute('SELECT last_seen FROM devices WHERE id=?', (identity.id,)).fetchone()
        busy = db.execute("SELECT 1 FROM control_jobs WHERE owner_id=? AND node_id=? AND state IN ('CLAIMED','CANCEL_REQUESTED')",
                          (user['id'], node['id'])).fetchone()
        queued = list(db.execute("SELECT occurrence,payload FROM control_jobs WHERE owner_id=? AND node_id=? AND state='QUEUED'",
                                 (user['id'], node['id'])))
    if (not scheduler or not scheduler['enabled'] or scheduler['revision'] != snapshot['revision']
            or not link or not device or device['last_seen'] is None
            or native.store.clock()-device['last_seen'] >= 45 or busy):
        return {'authorized': False}
    scope = json.loads(scheduler['scope'])
    if link['profile'] not in scope['profiles'] or 'WhatsApp' not in scope['platforms']:
        return {'authorized': False}
    # Revalidate the delegated scheduler owner too; an agent session does not resurrect it.
    delegated = native.broker.sessions.require_hash(scheduler['auth_session'])
    if delegated['id'] != user['id']:
        return {'authorized': False}
    queued_roots = {json.loads(job['payload']).get('original_occurrence', job['occurrence'])
                    for job in queued if json.loads(job['payload']).get('catalog_revision') == snapshot['revision']}
    candidates = [row for row in snapshot['schedule'] if row['device'] == link['profile']
                  and (row['state'] == 'PLANNED' or row['state'] == 'QUEUED' and row['id'] in queued_roots)
                  and row['due'] and supported(row)
                  and 'video' not in ''.join(row.get(k) or '' for k in ('system','album','album2')).casefold()
                  and datetime.fromisoformat(row['due_at'].replace('Z','+00:00')).timestamp() >= scheduler['from_at']]
    return {'authorized': bool(candidates)}
