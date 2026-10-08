"""Explicit one-step native reservations, never a worker or automatic retry."""
import json
from uuid import uuid4
from .control_media_modes import supported_media, requires_media_v2
from .control_recipe_state import active_recipe, get_recipe, recipe_view
from .control_recipe_proof import compatible_version
from .store import DomainError, digest, timestamp


def native_node(db, owner, publication, now):
    rows = db.execute('''SELECT n.id,n.last_seen,a.ready,a.enabled,m.ready AS media_ready,d.app_version
      FROM control_nodes n JOIN control_android_links a ON a.node_id=n.id AND a.owner_id=n.owner_id
      JOIN devices d ON d.id=a.device_id AND d.owner_id=a.owner_id
      LEFT JOIN control_android_media m ON m.device_id=a.device_id
      WHERE n.owner_id=? AND a.profile=? AND n.revoked=0 AND d.revoked=0''',
                      (owner, publication['device'])).fetchall()
    if len(rows) != 1:
        raise DomainError('ANDROID_EXECUTOR_NOT_READY', 409)
    node = rows[0]
    if not node['enabled'] or not node['ready'] or node['last_seen'] is None or not 0 <= now-node['last_seen'] < 45:
        raise DomainError('ANDROID_EXECUTOR_NOT_READY', 409)
    if requires_media_v2(publication) and not node['media_ready']:
        raise DomainError('ANDROID_MEDIA_CAPABILITY_REQUIRED', 409)
    if not compatible_version(node['app_version']):
        raise DomainError('ANDROID_RECIPE_VERSION_REQUIRED', 409)
    return node['id']


def response(db, row, step, now):
    job = db.execute('SELECT id,occurrence,state FROM control_jobs WHERE id=? AND owner_id=?',
                     (step['job_id'], row['owner_id'])).fetchone()
    return {'job_id': job['id'], 'occurrence_id': job['occurrence'], 'state': job['state'],
            'recipe': recipe_view(db, row, now)}


def launch_step(recipes, user, identity, step_id, client_key):
    broker, now, key = recipes.broker, recipes.store.clock(), str(client_key)
    with recipes.store.transaction() as db:
        row = get_recipe(db, user['id'], identity)
        step = db.execute('SELECT * FROM control_recipe_steps WHERE id=? AND recipe_id=?', (step_id, identity)).fetchone()
        if not step:
            raise DomainError('RECIPE_STEP_NOT_FOUND', 404)
        used = db.execute('SELECT id FROM control_recipe_steps WHERE recipe_id=? AND client_key=?', (identity, key)).fetchone()
        if used and used['id'] != step_id:
            raise DomainError('RECIPE_IDEMPOTENCY_CONFLICT', 409)
        # Even after cancel/release a repeated click only returns the original receipt.
        if step['job_id']:
            return response(db, row, step, now)
        if active_recipe(db, user['id']) != identity or row['state'] != 'ACTIVE':
            raise DomainError('RECIPE_STATE_INVALID', 409)
        view = recipe_view(db, row, now)
        refusal = {'DRAINING': 'RECIPE_DRAINING', 'COOLDOWN': 'RECIPE_COOLDOWN',
                   'IN_PROGRESS': 'RECIPE_IN_PROGRESS', 'BLOCKED': 'RECIPE_BLOCKED'}
        if view['state'] in refusal:
            raise DomainError(refusal[view['state']], 409)
        if view['state'] != 'READY' or view['next_step_id'] != step_id:
            raise DomainError('RECIPE_STEP_NOT_NEXT', 409)
        broker.catalog.revision(db, user['id'], row['revision'])
        publication = json.loads(step['publication'])
        if not supported_media(publication):
            raise DomainError('ADAPTER_NOT_VALIDATED', 409)
        node_id = native_node(db, user['id'], publication, now)
        job_id = str(uuid4())
        occurrence = digest('recipe:v1:' + identity + ':' + step_id)
        payload = {**publication, 'due_at': timestamp(now), 'catalog_revision': row['revision'],
                   'execution_origin': 'web_android_agent', 'web_triggered': True,
                   'recipe_id': identity, 'trial_id': step_id}
        db.execute('INSERT INTO control_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (job_id, user['id'], node_id, occurrence, json.dumps(payload), 'QUEUED', now, None, None, None))
        db.execute('UPDATE control_recipe_steps SET job_id=?,client_key=? WHERE id=?', (job_id, key, step_id))
        broker.terminal.emit(db, user['id'], 'QUEUED', publication['device'], publication['system'])
        step = db.execute('SELECT * FROM control_recipe_steps WHERE id=?', (step_id,)).fetchone()
        return response(db, row, step, now)
