"""A recipe requires the strict final-stage proof emitted by the native agent."""
import json
from .control_attempt_diagnostics import quantified_batch, with_observations
from .control_media_modes import media_count

MIN_VERSION = (0, 4, 15)


def receipt_diagnostics(db, owner, job_id):
    """Join the immutable split receipt using the same owner and attempt."""
    core = db.execute('SELECT value FROM control_attempt_diagnostics WHERE job_id=? AND owner_id=?',
                      (job_id, owner)).fetchone()
    if core is None:
        return None
    observations = db.execute('SELECT value FROM control_attempt_observations WHERE job_id=? AND owner_id=?',
                              (job_id, owner)).fetchone()
    return with_observations(json.loads(core['value']),
                             json.loads(observations['value']) if observations else None)


def compatible_version(value):
    try:
        parts = tuple(map(int, value.split('.')))
        return len(parts) == 3 and parts >= MIN_VERSION
    except (AttributeError, ValueError):
        return False


def verified_receipt(job, diagnostics, publication):
    return bool(job and job['completed'] is not None and job['state'] == 'CONFIRMED'
                and job['evidence'] == 'own_status_verified' and diagnostics
                and diagnostics.get('stage') in {'own_status_verification', 'complete'}
                and diagnostics.get('service_ready') is True
                and compatible_version(diagnostics.get('app_version'))
                and diagnostics.get('verification_method') in {'recent_visible', 'sequential_recent_visible_v1'}
                and quantified_batch(diagnostics, media_count(publication)))
