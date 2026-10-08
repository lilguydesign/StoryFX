"""Receipt-stage and version checks cannot be inferred from counts alone."""
import pytest
from test_attempt_diagnostics import diagnostics
from storyfx_server.control_recipe_proof import verified_receipt


@pytest.mark.parametrize('field,value', [('stage', 'preflight'), ('app_version', '0.4.14'),
                                      ('service_ready', False), ('verification_method', 'recent_rows')])
def test_recipe_rejects_nonfinal_or_legacy_proof(field, value):
    job = {'state': 'CONFIRMED', 'evidence': 'own_status_verified', 'completed': 100}
    publication = {'engine': 'multi', 'count': 3}
    proof = {**diagnostics(), 'app_version': '0.4.15', 'verification_method': 'recent_visible'}
    assert verified_receipt(job, proof, publication)
    assert not verified_receipt(job, {**proof, field: value}, publication)


@pytest.mark.parametrize('stage', ['own_status_verification', 'complete'])
def test_actual_native_final_stage_and_explicit_complete_are_supported(stage):
    job = {'state': 'CONFIRMED', 'evidence': 'own_status_verified', 'completed': 100}
    proof = {**diagnostics(), 'app_version': '0.4.15', 'verification_method': 'recent_visible', 'stage': stage}
    assert verified_receipt(job, proof, {'engine': 'multi', 'count': 3})
