"""Synthetic evidence only; no network, phone or provider calls."""
from copy import deepcopy
import pytest
from pydantic import ValidationError
from storyfx_server.control_sequential_proof import (
    SequentialProof, METHOD, planned_counts, valid_shape, quantified_sequential, valid_for_job,
)


def proof():
    return dict(contract_version=1, planned_counts=[9, 2], verified_counts=[9, 2],
        baseline_elapsed_ms=[0, 80000], baseline_aged_rows=[10, 10], verified_elapsed_ms=[20000, 100000])


def diagnostics():
    return dict(app_version='0.4.18', account_verified=False, expected_count=11, selected_count=11,
        verified_count=11, provider_package='whatsapp_business', verification_method=METHOD, sequential_proof=proof())


def test_complete_separated_counts_and_exact_plan():
    assert valid_shape(proof(), 11, complete=True)
    assert quantified_sequential(diagnostics(), 11)
    assert valid_for_job(diagnostics(), dict(engine='multi', count=11, recipe_id='synthetic'), 'CONFIRMED')
    assert planned_counts(dict(engine='intro+multi', count=11)) == [1, 9, 2]
    assert planned_counts(dict(engine='multi', count=30)) == [9, 9, 9, 3]


@pytest.mark.parametrize('key,value', [
    ('verified_counts', [9]), ('verified_counts', [9, 3]),
    ('baseline_elapsed_ms', [0, 10000]), ('baseline_aged_rows', [10, 8]),
    ('verified_elapsed_ms', [0, 100000]), ('verified_elapsed_ms', [20000, 780000]),
    ('planned_counts', [10, 1]), ('planned_counts', [True, 2]), ('contract_version', True),
])
def test_incomplete_ambiguous_and_coerced_proofs_cannot_confirm(key, value):
    p=proof();p[key]=value
    assert not valid_shape(p, 11, complete=True)
    d=diagnostics();d['sequential_proof']=p
    assert not quantified_sequential(d, 11)


def test_partial_intent_is_recordable_but_never_confirmed():
    d=diagnostics();p=d['sequential_proof']
    p.update(verified_counts=[9], verified_elapsed_ms=[20000])
    d.update(verified_count=9, verification_method='none')
    assert valid_shape(p,11,complete=False)
    assert valid_for_job(d,dict(engine='multi',count=11,recipe_id='synthetic'),'NEEDS_REVIEW')
    assert not quantified_sequential(d,11)
    assert not valid_for_job(d,dict(engine='multi',count=11,recipe_id='synthetic'),'CONFIRMED')
    d['verified_count'] = 11
    assert not valid_for_job(d,dict(engine='multi',count=11,recipe_id='synthetic'),'NEEDS_REVIEW')


def test_manual_only_version_and_media_mode_boundaries():
    d=diagnostics()
    assert not valid_for_job(d,dict(engine='multi',count=11),'CONFIRMED')
    assert not valid_for_job(d,dict(engine='intro+multi',count=10,recipe_id='synthetic'),'CONFIRMED')
    d['app_version']='0.4.17'
    assert not quantified_sequential(d,11)
    assert not valid_for_job(d,dict(engine='multi',count=11,recipe_id='synthetic'),'CONFIRMED')


def test_model_rejects_boolean_integer_coercion_and_private_fields():
    for key, value in [('contract_version', True), ('verified_counts', [True, 2]), ('media_uri', 'synthetic')]:
        p=proof();p[key]=value
        with pytest.raises(ValidationError):SequentialProof.model_validate(p)
