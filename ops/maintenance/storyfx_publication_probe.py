"""Read bounded observation evidence; never dispatch, retry or read phone contents."""
import json
import math
from pathlib import Path
import time

STATE_PATH = Path('/opt/formafx/storyfx/state/observation-state.json')
MAX_STATE_BYTES = 128 * 1024 * 1024
VERDICTS = (
    'confirmed_agent', 'confirmed_legacy_unverified_count', 'uncertain',
    'failed_before_send', 'adapter_not_validated', 'outside_media_rollout',
    'outside_active_scheduler', 'late', 'waiting',
)


def result(status, reason, metrics=None):
    return {
        'id': 'storyfx_publication_outcomes', 'application': 'StoryFX',
        'label': 'StoryFX — résultats de publication', 'status': status,
        'reason_code': reason,
        'detail': 'Résultats observés par le serveur ; aucune reprise automatique.',
        'metrics': dict(metrics or {}, publication_verified=False,
                        total_autonomy_verified=False, phone_actions=False),
        'notifications_sent': False, 'business_mutations': False,
        'real_send_triggered': False,
    }


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def evaluate(state, now):
    if not isinstance(state, dict) or state.get('read_only') is not True:
        return result('unknown', 'STORYFX_PUBLICATION_PROOF_MISSING')
    observations = state.get('observations')
    if not isinstance(observations, list) or not observations or not isinstance(observations[-1], dict):
        return result('unknown', 'STORYFX_PUBLICATION_PROOF_MISSING')
    last = observations[-1]
    if last.get('read_only') is not True or last.get('real_send_triggered_by_observer') is not False:
        return result('incident', 'STORYFX_OBSERVER_BOUNDARY_INVALID')
    observed = last.get('observed_unix')
    complete = state.get('complete')
    start, end = state.get('start_unix'), state.get('end_unix')
    if (not all(number(value) for value in (now, observed, start, end))
            or not 0 < end - start <= 7 * 86400 or type(complete) is not bool
            or observed < start or observed > now or (complete and observed < end + 900)):
        return result('unknown', 'STORYFX_PUBLICATION_WINDOW_INVALID')
    totals = last.get('totals')
    if not isinstance(totals, dict) or any(
            type(value) is not int or not 0 <= value <= 1000000 for value in totals.values()):
        return result('unknown', 'STORYFX_PUBLICATION_COUNTS_INVALID')
    if any(key not in VERDICTS for key in totals):
        return result('unknown', 'STORYFX_PUBLICATION_VERDICT_UNKNOWN')
    counts = {key: totals.get(key, 0) for key in VERDICTS}
    scheduler = last.get('scheduler_enabled')
    if type(scheduler) is not bool or type(last.get('whatsapp_scope_violation')) is not bool:
        return result('unknown', 'STORYFX_PUBLICATION_PROOF_INVALID')
    metrics = {'observed_unix': observed, 'complete': complete,
               'scheduler_enabled': scheduler, 'totals': counts,
               'freshness_seconds': int(now - observed), 'timezone': 'Africa/Douala',
               'agent_confirmations_are_delivery_proof': False}
    if last['whatsapp_scope_violation']:
        return result('incident', 'STORYFX_SCOPE_CHANGED', metrics)
    if not complete and now - observed > 2400:
        return result('incident', 'STORYFX_PUBLICATION_PROOF_STALE', metrics)
    for key, reason in (
        ('uncertain', 'STORYFX_PUBLICATION_UNCERTAIN'),
        ('failed_before_send', 'STORYFX_PUBLICATION_FAILED_BEFORE_SEND'),
        ('late', 'STORYFX_PUBLICATION_LATE'),
    ):
        if counts[key]:
            return result('incident', reason, metrics)
    if not sum(counts.values()):
        return result('waiting', 'STORYFX_NO_DUE_PUBLICATION', metrics)
    if counts['waiting']:
        return result('waiting', 'STORYFX_PUBLICATION_WAITING', metrics)
    excluded = sum(counts[key] for key in (
        'adapter_not_validated', 'outside_media_rollout', 'outside_active_scheduler'))
    if excluded:
        return result('waiting', 'STORYFX_PUBLICATION_EXCLUSIONS_PRESENT', metrics)
    return result('ok', 'STORYFX_NO_PUBLICATION_INCIDENT_OBSERVED', metrics)


def read_state(path):
    if path.stat().st_size > MAX_STATE_BYTES:
        raise ValueError('OBSERVATION_TOO_LARGE')
    with path.open('rb') as source:
        content = source.read(MAX_STATE_BYTES + 1)
    if len(content) > MAX_STATE_BYTES:
        raise ValueError('OBSERVATION_TOO_LARGE')
    return json.loads(content)


def collect(now=None, *, read=read_state, path=STATE_PATH):
    clock = time.time() if now is None else now.timestamp() if hasattr(now, 'timestamp') else now
    try:
        return evaluate(read(path), clock)
    except (OSError, ValueError, TypeError, OverflowError):
        return result('unknown', 'STORYFX_PUBLICATION_PROOF_MISSING')


if __name__ == '__main__':
    print(json.dumps(collect()))
