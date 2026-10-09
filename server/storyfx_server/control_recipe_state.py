"""Persistent manual validation isolation and read-only progress projections."""
import json
from .control_media_modes import media_count
from .control_recipe_proof import receipt_diagnostics, verified_receipt
from .store import DomainError, timestamp


def initialize(store):
    with store.transaction() as db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS control_recipes (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, client_key TEXT NOT NULL,
            request_hash TEXT NOT NULL, revision INTEGER NOT NULL, executor TEXT NOT NULL,
            state TEXT NOT NULL, created REAL NOT NULL, started REAL, released REAL,
            scheduler_before TEXT, UNIQUE(owner_id,client_key));
          CREATE TABLE IF NOT EXISTS control_recipe_steps (
            id TEXT PRIMARY KEY, recipe_id TEXT NOT NULL, position INTEGER NOT NULL,
            row_id TEXT NOT NULL, publication TEXT NOT NULL, job_id TEXT UNIQUE,
            client_key TEXT, UNIQUE(recipe_id,position), UNIQUE(recipe_id,row_id));
          CREATE TABLE IF NOT EXISTS control_recipe_locks (
            owner_id TEXT PRIMARY KEY, recipe_id TEXT UNIQUE NOT NULL);
          CREATE TABLE IF NOT EXISTS control_recipe_boundaries (
            owner_id TEXT PRIMARY KEY, not_before REAL NOT NULL,
            automation_ready INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS control_recipe_validation (
            owner_id TEXT PRIMARY KEY, recipe_id TEXT NOT NULL,
            revision INTEGER NOT NULL, row_ids TEXT NOT NULL);
          CREATE UNIQUE INDEX IF NOT EXISTS control_recipe_step_request
            ON control_recipe_steps(recipe_id,client_key) WHERE client_key IS NOT NULL;
        ''')


def active_recipe(db, owner):
    row = db.execute('SELECT recipe_id FROM control_recipe_locks WHERE owner_id=?', (owner,)).fetchone()
    return row['recipe_id'] if row else None


def assert_unlocked(db, owner):
    if active_recipe(db, owner):
        raise DomainError('MANUAL_RECIPE_ACTIVE', 409)


def boundary(db, owner):
    row = db.execute('SELECT * FROM control_recipe_boundaries WHERE owner_id=?', (owner,)).fetchone()
    return dict(row) if row else None


def scheduler_hold(db, owner):
    if active_recipe(db, owner):
        return 'MANUAL_RECIPE_ACTIVE'
    limit = boundary(db, owner)
    return 'RECIPE_VALIDATION_REQUIRED' if limit and not limit['automation_ready'] else ''


def assert_validated_scope(db, owner, revision, row_ids):
    if not boundary(db, owner):
        return
    proof = db.execute('SELECT revision,row_ids FROM control_recipe_validation WHERE owner_id=?', (owner,)).fetchone()
    if not proof or proof['revision'] != revision or not row_ids or not set(row_ids) <= set(json.loads(proof['row_ids'])):
        raise DomainError('RECIPE_SCOPE_NOT_VALIDATED', 409)


def get_recipe(db, owner, identity):
    row = db.execute('SELECT * FROM control_recipes WHERE id=? AND owner_id=?', (identity, owner)).fetchone()
    if not row:
        raise DomainError('RECIPE_NOT_FOUND', 404)
    return row


def pending_count(db, owner, recipe=None):
    sql = "SELECT COUNT(*) FROM control_jobs WHERE owner_id=? AND completed IS NULL AND state IN ('QUEUED','CLAIMED','CANCEL_REQUESTED','NEEDS_REVIEW')"
    values = [owner]
    if recipe:
        sql += " AND COALESCE(json_extract(payload,'$.recipe_id'),'')<>?"
        values.append(recipe)
    return db.execute(sql, values).fetchone()[0]


def latest_verified_at(db, owner):
    for row in db.execute('''SELECT j.id,j.state,j.evidence,j.completed,j.payload FROM control_jobs j
      JOIN control_attempt_diagnostics d ON d.job_id=j.id AND d.owner_id=j.owner_id
      WHERE j.owner_id=? AND j.state='CONFIRMED' AND j.evidence='own_status_verified'
      AND j.completed IS NOT NULL ORDER BY j.completed DESC''', (owner,)):
        value = receipt_diagnostics(db, owner, row['id'])
        if verified_receipt(row, value, json.loads(row['payload'])):
            return row['completed']
    return None


def steps_view(db, row):
    steps = []
    for step in db.execute('SELECT * FROM control_recipe_steps WHERE recipe_id=? ORDER BY position', (row['id'],)):
        publication = json.loads(step['publication'])
        job = db.execute('SELECT * FROM control_jobs WHERE id=? AND owner_id=?', (step['job_id'], row['owner_id'])).fetchone()
        diagnostics = receipt_diagnostics(db, row['owner_id'], step['job_id'])
        verified = verified_receipt(job, diagnostics, publication)
        steps.append({'id': step['id'], 'position': step['position'], 'row_id': step['row_id'],
                      'publication': publication, 'expected_media_count': media_count(publication),
                      'job_id': step['job_id'], 'state': job['state'] if job else 'NOT_REQUESTED',
                      'verified': verified, 'completed_at': timestamp(job['completed']) if job else None,
                      'completed': job['completed'] if job else None})
    return steps


def recipe_view(db, row, now):
    steps = steps_view(db, row)
    external = pending_count(db, row['owner_id'], row['id'])
    held = active_recipe(db, row['owner_id']) == row['id']
    state, reason, next_id, next_at = row['state'], '', None, None
    requested = [step for step in steps if step['job_id']]
    remaining = [step for step in steps if not step['job_id']]
    bad = next((step for step in requested if step['state'] in ('NEEDS_REVIEW', 'FAILED_BEFORE_PUBLICATION', 'CANCELLED')
                or step['completed'] is not None and not step['verified']), None)
    if state == 'ACTIVE':
        if bad:
            state, reason = 'BLOCKED', 'RECIPE_PROOF_INCOMPLETE' if bad['state'] == 'CONFIRMED' else 'RECIPE_RESULT_UNVERIFIED'
        elif any(step['completed'] is None for step in requested):
            state = 'IN_PROGRESS'
        elif external:
            state = 'DRAINING'
        elif not remaining:
            state = 'PASSED'
        else:
            next_id = remaining[0]['id']
            limit = boundary(db, row['owner_id'])
            previous = latest_verified_at(db, row['owner_id'])
            next_at = max(limit['not_before'] if limit else 0, previous + 300 if previous is not None else now)
            state = 'COOLDOWN' if next_at > now else 'READY'
    result = {'id': row['id'], 'client_key': row['client_key'], 'revision': row['revision'],
              'executor': row['executor'], 'state': state, 'created_at': timestamp(row['created']),
              'started_at': timestamp(row['started']), 'released_at': timestamp(row['released']),
              'lock_held': held, 'external_pending': external, 'next_step_id': next_id,
              'next_allowed_at': timestamp(next_at), 'block_reason': reason,
              'scheduler_before': json.loads(row['scheduler_before']) if row['scheduler_before'] else None,
              'steps': [{key: value for key, value in step.items() if key != 'completed'} for step in steps],
              'all_steps_verified': bool(steps and all(step['verified'] for step in steps))}
    return result
