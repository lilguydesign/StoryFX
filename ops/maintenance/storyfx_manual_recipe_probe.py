"""Observe explicit manual validation; never launch, resume or retry a step."""
from datetime import datetime
import json
import time
from storyfx_publication_probe import STATE_PATH, number, read_state

STATES = {'none', 'draft', 'draining', 'ready', 'in_progress', 'cooldown',
          'blocked', 'passed', 'cancelled', 'released'}
COUNTS = ('pending_attempts', 'external_pending', 'total_steps', 'verified_steps',
          'failed_steps', 'uncertain_steps', 'incomplete_proof_steps', 'interval_violation_steps')
FLAGS = ('started', 'lock_held', 'automation_ready', 'scheduler_enabled')
LOCKED_STATES = {'draining', 'ready', 'in_progress', 'cooldown', 'blocked', 'passed'}


def result(status, reason, metrics=None):
    return {'id': 'storyfx_manual_recipe', 'application': 'StoryFX',
            'label': 'StoryFX — recette manuelle', 'status': status, 'reason_code': reason,
            'detail': 'État agrégé observé ; attente manuelle sans échéance automatique ni rejeu.',
            'metrics': dict(metrics or {}, total_autonomy_verified=False,
                            account_identity_verified=False, phone_actions=False),
            'notifications_sent': False, 'business_mutations': False, 'real_send_triggered': False}


def timestamp(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError('INVALID_TIMESTAMP')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or not number(parsed.timestamp()):
        raise ValueError('INVALID_TIMESTAMP')
    return int(parsed.timestamp())


def evaluate(state, now):
    if not isinstance(state, dict) or state.get('read_only') is not True:
        return result('unknown', 'STORYFX_RECIPE_PROOF_MISSING')
    observations = state.get('observations')
    if not isinstance(observations, list) or not observations or not isinstance(observations[-1], dict):
        return result('unknown', 'STORYFX_RECIPE_PROOF_MISSING')
    last = observations[-1]
    if last.get('read_only') is not True or last.get('real_send_triggered_by_observer') is not False:
        return result('incident', 'STORYFX_RECIPE_OBSERVER_BOUNDARY_INVALID')
    observed = last.get('observed_unix')
    if not number(now) or not number(observed) or observed > now:
        return result('unknown', 'STORYFX_RECIPE_CLOCK_INVALID')
    # Completed historical observation windows do not prove a current recipe state.
    if now - observed > 2400:
        return result('unknown', 'STORYFX_RECIPE_PROOF_STALE')
    value = last.get('manual_validation')
    if not isinstance(value, dict):
        return result('unknown', 'STORYFX_RECIPE_SCHEMA_UNAVAILABLE')
    phase = value.get('state')
    if (type(value.get('contract_version')) is not int or value['contract_version'] != 1
            or not isinstance(phase, str) or phase not in STATES
            or any(type(value.get(key)) is not bool for key in FLAGS)
            or any(type(value.get(key)) is not int or not 0 <= value[key] <= 1000000 for key in COUNTS)):
        return result('unknown', 'STORYFX_RECIPE_CONTRACT_INVALID')
    try:
        next_at = timestamp(value['next_allowed_at'])
        resume_at = timestamp(value['resume_not_before'])
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        return result('unknown', 'STORYFX_RECIPE_CONTRACT_INVALID')
    if (type(last.get('scheduler_enabled')) is not bool
            or value['scheduler_enabled'] != last['scheduler_enabled']
            or value['external_pending'] > value['pending_attempts']
            or any(value[key] > value['total_steps'] for key in
                   ('verified_steps', 'failed_steps', 'uncertain_steps',
                    'incomplete_proof_steps', 'interval_violation_steps'))):
        return result('unknown', 'STORYFX_RECIPE_CONTRACT_INVALID')
    metrics = {key: value[key] for key in (*COUNTS, *FLAGS)}
    metrics.update(state=phase, observed_unix=observed, freshness_seconds=int(now - observed),
                   next_allowed_unix=next_at, resume_not_before_unix=resume_at,
                   minimum_interval_seconds=300)
    required = phase in LOCKED_STATES or phase == 'cancelled' and value['started']
    if (required and not value['lock_held'] or phase in {'none', 'draft', 'released'} and value['lock_held']
            or value['lock_held'] and (not value['started'] or value['automation_ready'])):
        return result('incident', 'STORYFX_RECIPE_LOCK_INCONSISTENT', metrics)
    for key, reason in (
        ('interval_violation_steps', 'STORYFX_RECIPE_INTERVAL_VIOLATION'),
        ('uncertain_steps', 'STORYFX_RECIPE_UNCERTAIN'),
        ('failed_steps', 'STORYFX_RECIPE_FAILED'),
        ('incomplete_proof_steps', 'STORYFX_RECIPE_PROOF_INCOMPLETE'),
    ):
        if value[key]:
            return result('incident', reason, metrics)
    if phase == 'passed' and (not value['total_steps'] or value['verified_steps'] != value['total_steps']
                              or value['pending_attempts']):
        return result('incident', 'STORYFX_RECIPE_PASS_INCONSISTENT', metrics)
    if phase == 'blocked':
        return result('incident', 'STORYFX_RECIPE_BLOCKED', metrics)
    if phase == 'none':
        if value['started'] or value['total_steps']:
            return result('unknown', 'STORYFX_RECIPE_CONTRACT_INVALID', metrics)
        return result('ok', 'STORYFX_RECIPE_NOT_CONFIGURED', metrics)
    if phase == 'passed':
        return result('ok', 'STORYFX_RECIPE_STEPS_VERIFIED', metrics)
    # Scheduler enabled alone is normal under a lock and after an explicit restart.
    return result('waiting', 'STORYFX_RECIPE_' + phase.upper(), metrics)


def collect(now=None, *, read=read_state, path=STATE_PATH):
    clock = time.time() if now is None else now.timestamp() if hasattr(now, 'timestamp') else now
    try:
        return evaluate(read(path), clock)
    except (OSError, ValueError, TypeError, OverflowError):
        return result('unknown', 'STORYFX_RECIPE_PROOF_MISSING')


if __name__ == '__main__':
    print(json.dumps(collect()))
