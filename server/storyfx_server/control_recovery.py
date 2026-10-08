"""Explicit owner retries for proven pre-send failures; original audit is immutable."""
from datetime import datetime
from hashlib import sha256
import json
from uuid import uuid4
from zoneinfo import ZoneInfo
from .control_android import executors
from .control_publications import supported
from .store import DomainError
from .control_status_reviews import empty_review
from .control_recipe_state import assert_unlocked

# Generic failures require fresh empty-own-status review; picker/send failures stay excluded.
SAFE_FAILURES = frozenset({'album_media_unavailable', 'provider_not_ready',
                           'updates_navigation_failed', 'own_status_unavailable'})


def eligible(report):
    return (report['state'] == 'FAILED_BEFORE_PUBLICATION'
            and report['evidence'] in SAFE_FAILURES
            and report['publication'].get('execution_origin') == 'web_android_agent')


def repeat(broker, user, identity, revision):
    return repeat_many(broker, user, [identity], revision)['jobs'][0]


def repeat_many(broker, user, identities, revision):
    if not 1 <= len(identities) <= 20 or len(set(identities)) != len(identities):
        raise DomainError('RETRY_SELECTION_INVALID', 422)
    snapshot = broker.snapshot(user)
    if snapshot['revision'] != revision:
        raise DomainError('CONFIGURATION_CHANGED', 409)
    with broker.store.transaction() as db:
        assert_unlocked(db, user['id'])
        broker.catalog.revision(db, user['id'], revision)
        jobs = [_repeat(db, broker, user, identity, revision, snapshot) for identity in identities]
    return {'jobs':jobs,'original_audit_preserved':True}


def _repeat(db, broker, user, identity, revision, snapshot):
    parent = db.execute('SELECT * FROM control_jobs WHERE id=? AND owner_id=?',
                        (identity, user['id'])).fetchone()
    if not parent:
        raise DomainError('PUBLICATION_NOT_FOUND', 404)
    reviewed_empty = empty_review(db, parent, broker.store.clock())
    if not eligible(broker.report(parent)) and not reviewed_empty:
        raise DomainError('PUBLICATION_REVIEW_REQUIRED', 409)
    if db.execute("SELECT 1 FROM control_jobs WHERE owner_id=? AND json_extract(payload,'$.retry_parent')=?",
                  (user['id'], identity)).fetchone():
        raise DomainError('RETRY_ALREADY_REQUESTED', 409)
    original = json.loads(parent['payload'])
    if original.get('recipe_id'):
        raise DomainError('PUBLICATION_REVIEW_REQUIRED', 409)
    root = original.get('original_occurrence', parent['occurrence'])
    planned = [v for v in snapshot['schedule'] if v['id'] == root]
    if len(planned) != 1 or not supported(planned[0]):
        raise DomainError('PUBLICATION_PLAN_CHANGED', 409)
    value = planned[0]
    due = datetime.fromisoformat(value['due_at'].replace('Z', '+00:00'))
    now = datetime.fromtimestamp(broker.store.clock(), ZoneInfo('Africa/Douala'))
    if due.timestamp() > broker.store.clock() or due.astimezone(now.tzinfo).date() != now.date():
        raise DomainError('RETRY_WINDOW_INVALID', 409)
    nodes = executors(snapshot, value)
    if len(nodes) != 1 or nodes[0].get('executor') != 'android_whatsapp_images_v1':
        raise DomainError('ANDROID_EXECUTOR_NOT_READY', 409)
    if reviewed_empty and nodes[0]['id'] != parent['node_id']:
        raise DomainError('ANDROID_EXECUTOR_NOT_READY', 409)
    node = db.execute('SELECT last_seen,revoked FROM control_nodes WHERE id=? AND owner_id=?',
                      (nodes[0]['id'], user['id'])).fetchone()
    link = db.execute('SELECT ready,enabled FROM control_android_links WHERE node_id=? AND owner_id=?',
                      (nodes[0]['id'], user['id'])).fetchone()
    if (not node or node['revoked'] or node['last_seen'] is None or
            broker.store.clock()-node['last_seen'] >= 45 or not link or not link['ready'] or not link['enabled']):
        raise DomainError('ANDROID_EXECUTOR_NOT_READY', 409)
    rows = [row for row in snapshot['collections']['matrix'] if row['id'] == value['row_id']]
    if len(rows) != 1 or any(original.get(key) != rows[0].get(key) for key in
                            ('id', 'device', 'platform', 'system', 'engine', 'album', 'album2',
                             'count', 'page', 'page_name')):
        raise DomainError('PUBLICATION_PLAN_CHANGED', 409)
    child = str(uuid4())
    depth = original.get('retry_depth', 0)
    if type(depth) is not int or not 0 <= depth < 64:
        raise DomainError('PUBLICATION_REVIEW_REQUIRED', 409)
    occurrence = sha256(('manual-retry:' + parent['occurrence'] + ':' + child).encode()).hexdigest()
    payload = {**rows[0], 'due_at':value['due_at'], 'catalog_revision':revision,
               'execution_origin':'web_android_agent', 'web_triggered':True,
               'retry_parent':identity, 'original_occurrence':root, 'retry_depth':depth+1}
    db.execute('INSERT INTO control_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
               (child, user['id'], nodes[0]['id'], occurrence, json.dumps(payload),
                'QUEUED', broker.store.clock(), None, None, None))
    broker.terminal.emit(db, user['id'], 'MANUAL_RETRY_QUEUED', value['device'], value['system'])
    return {'job_id':child, 'occurrence_id':occurrence, 'parent_job_id':identity,
            'state':'QUEUED', 'original_audit_preserved':True}
