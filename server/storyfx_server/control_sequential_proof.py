"""Separated native quantity evidence. Neither row positions nor counts identify media/accounts."""
from pydantic import Field, StrictInt
from .control_models import Strict

METHOD = 'sequential_recent_visible_v1'


class SequentialProof(Strict):
    contract_version: int = Field(strict=True, ge=1, le=1)
    planned_counts: list[StrictInt] = Field(min_length=2, max_length=5)
    verified_counts: list[StrictInt] = Field(max_length=5)
    baseline_elapsed_ms: list[StrictInt] = Field(max_length=5)
    baseline_aged_rows: list[StrictInt] = Field(max_length=5)
    verified_elapsed_ms: list[StrictInt] = Field(max_length=5)


def planned_counts(payload):
    count = payload.get('count')
    if type(count) is not int or not 1 <= count <= 30:
        return None
    mode = payload.get('engine')
    parts = [count] if mode == 'multi' else [1, count] if mode == 'intro+multi' else []
    if not parts or not 10 <= sum(parts) <= 30:
        return None
    return [size for part in parts for size in [9] * (part // 9) + ([part % 9] if part % 9 else [])]


def valid_shape(proof, expected, *, complete):
    if type(proof) is not dict or set(proof) != {
            'contract_version', 'planned_counts', 'verified_counts', 'baseline_elapsed_ms',
            'baseline_aged_rows', 'verified_elapsed_ms'} or type(proof['contract_version']) is not int or proof['contract_version'] != 1:
        return False
    plan, counts, baseline, aged, finished = (proof[k] for k in (
        'planned_counts', 'verified_counts', 'baseline_elapsed_ms', 'baseline_aged_rows', 'verified_elapsed_ms'))
    if any(type(xs) is not list for xs in (plan, counts, baseline, aged, finished)):
        return False
    if not 2 <= len(plan) <= 5 or any(type(n) is not int or not 1 <= n <= 9 for n in plan) or sum(plan) != expected:
        return False
    done, started = len(counts), len(baseline)
    if counts != plan[:done] or any(type(n) is not int for n in counts) or done > len(plan):
        return False
    if len(finished) != done or len(aged) != started or started not in {done, done + 1} or started > len(plan):
        return False
    if any(type(n) is not int or not 0 <= n < 780000 for n in baseline + finished):
        return False
    if any(type(n) is not int or not 0 <= n <= 2500 for n in aged):
        return False
    if any(finished[i] <= baseline[i] for i in range(done)):
        return False
    if any(baseline[i] <= finished[i - 1] or aged[i] < plan[i - 1] for i in range(1, started)):
        return False
    return not complete or counts == plan and started == done


def compatible_version(value):
    try:
        parts = tuple(map(int, value.split('.')))
        return len(parts) == 3 and parts >= (0, 4, 18)
    except (AttributeError, ValueError):
        return False


def quantified_sequential(value, expected):
    return bool(type(expected) is int and 10 <= expected <= 30 and value and value.get('verification_method') == METHOD
        and compatible_version(value.get('app_version'))
        and value.get('account_verified') is False
        and value.get('expected_count') == value.get('selected_count') == value.get('verified_count') == expected
        and value.get('provider_package') == 'whatsapp_business'
        and valid_shape(value.get('sequential_proof'), expected, complete=True))


def valid_for_job(value, payload, state):
    proof = value.get('sequential_proof')
    if proof is None:
        return value.get('verification_method') != METHOD
    expected = sum(planned_counts(payload) or [])
    return bool(expected and payload.get('recipe_id') and compatible_version(value.get('app_version'))
        and proof.get('planned_counts') == planned_counts(payload)
        and valid_shape(proof, expected, complete=state == 'CONFIRMED')
        and value.get('expected_count') == value.get('selected_count') == expected
        and value.get('verified_count') == sum(proof['verified_counts'])
        and value.get('account_verified') is False
        and (value.get('verification_method') == 'none' and state != 'CONFIRMED'
             or value.get('verification_method') == METHOD and quantified_sequential(value, expected)))
