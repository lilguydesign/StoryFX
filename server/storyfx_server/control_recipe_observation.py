"""Read-only aggregate manual-validation evidence, without identities or content."""
from .control_recipe_state import active_recipe, boundary, pending_count, recipe_view
from .store import timestamp


def held_intervals(db, owner, now, tables):
    if 'control_recipes' not in tables:
        return []
    return [(row['started'], row['released'] if row['released'] is not None else now)
            for row in db.execute('SELECT started,released FROM control_recipes WHERE owner_id=? AND started IS NOT NULL', (owner,))]


def manual_validation(db, owner, now, tables):
    required = {'control_recipes', 'control_recipe_steps', 'control_recipe_locks',
                'control_recipe_boundaries', 'control_attempt_diagnostics'}
    if not required <= tables:
        return None
    held = active_recipe(db, owner)
    row = (db.execute('SELECT * FROM control_recipes WHERE owner_id=? AND id=?', (owner, held)).fetchone()
           if held else db.execute('SELECT * FROM control_recipes WHERE owner_id=? ORDER BY created DESC,id LIMIT 1', (owner,)).fetchone())
    limit = boundary(db, owner)
    scheduler = db.execute('SELECT enabled FROM control_schedulers WHERE owner_id=?', (owner,)).fetchone()
    view = recipe_view(db, row, now) if row else None
    steps = view['steps'] if view else []
    intervals = 0
    for previous, step in zip(steps, steps[1:]):
        if not step['job_id']:
            continue
        created = db.execute('SELECT created FROM control_jobs WHERE id=? AND owner_id=?', (step['job_id'], owner)).fetchone()
        prior = db.execute('SELECT completed FROM control_jobs WHERE id=? AND owner_id=?', (previous['job_id'], owner)).fetchone()
        if created and (not previous['verified'] or not prior or prior['completed'] is None or created['created'] < prior['completed'] + 300):
            intervals += 1
    return {'contract_version': 1, 'state': view['state'].lower() if view else 'none',
            'started': bool(row and row['started'] is not None),
            'lock_held': bool(held), 'pending_attempts': pending_count(db, owner),
            'external_pending': view['external_pending'] if view else 0,
            'total_steps': len(steps), 'verified_steps': sum(s['verified'] for s in steps),
            'failed_steps': sum(s['state'] == 'FAILED_BEFORE_PUBLICATION' for s in steps),
            'uncertain_steps': sum(s['state'] == 'NEEDS_REVIEW' for s in steps),
            'incomplete_proof_steps': sum(s['state'] == 'CONFIRMED' and not s['verified'] for s in steps),
            'next_allowed_at': view['next_allowed_at'] if view else None,
            'automation_ready': bool(limit and limit['automation_ready']),
            'resume_not_before': timestamp(limit['not_before']) if limit and limit['not_before'] else None,
            'scheduler_enabled': bool(scheduler and scheduler['enabled']),
            'interval_violation_steps': intervals}
