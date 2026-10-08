"""A recipe requires the strict final-stage proof emitted by the native agent."""
from .control_attempt_diagnostics import quantified_batch
from .control_media_modes import media_count

MIN_VERSION = (0, 4, 15)


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
                and diagnostics.get('verification_method') == 'recent_visible'
                and quantified_batch(diagnostics, media_count(publication)))
