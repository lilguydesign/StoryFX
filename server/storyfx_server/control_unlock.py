"""Read-only wake permission for an exact scheduled plan or explicit manual start."""
from datetime import datetime
import json
from .control_publications import supported
from .control_media_modes import requires_media_v2
from .control_recipe_unlock import manual_unlock


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
        device = db.execute('SELECT last_seen,app_version FROM devices WHERE id=?', (identity.id,)).fetchone()
        busy = db.execute("SELECT 1 FROM control_jobs WHERE owner_id=? AND node_id=? AND state IN ('CLAIMED','CANCEL_REQUESTED')",
                          (user['id'], node['id'])).fetchone()
        queued = list(db.execute("SELECT occurrence,payload FROM control_jobs WHERE owner_id=? AND node_id=? AND state='QUEUED'",
                                 (user['id'], node['id'])))
        now = native.store.clock()
        if (not link or not device or device['last_seen'] is None
                or not 0 <= now-device['last_seen'] < 45 or busy):
            return {'authorized': False}
        manual = manual_unlock(db, user['id'], link['profile'], node, device, snapshot, now)
        if manual is not None:
            return {'authorized': manual}
    if not scheduler or not scheduler['enabled'] or scheduler['revision'] != snapshot['revision']:
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
                  and (not requires_media_v2(row) or node['media_modes_ready'] and
                       datetime.fromisoformat(row['due_at'].replace('Z','+00:00')).timestamp() >= native.media_enabled_from)
                  and datetime.fromisoformat(row['due_at'].replace('Z','+00:00')).timestamp() >= scheduler['from_at']]
    return {'authorized': bool(candidates)}
