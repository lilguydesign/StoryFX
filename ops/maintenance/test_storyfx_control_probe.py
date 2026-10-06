"""Missing evidence must not be promoted to publication or endurance success."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('control_probe', Path(__file__).with_name('storyfx_control_probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_contract_and_private_boundary():
    value = {'control_center_mode': 'windows_bridge', 'windows_publication_enabled': True,
             'android_publication_enabled': True, 'android_executor': 'whatsapp_images_pilot', 'status': 'ok', 'database_ok': True,
             'scheduler_available': True, 'scheduler_worker_ok': True, 'scheduler_tick_seconds': 10}
    result = probe.evaluate(value)
    assert result['status'] == 'ok'
    assert result['metrics']['publication_verified'] is False
    assert result['metrics']['windows_executor_observed'] is False
    assert probe.evaluate({**value, 'android_publication_enabled': False})['status'] == 'incident'
    legacy = {key: val for key, val in value.items() if key != 'android_executor'}
    assert probe.evaluate({**legacy, 'android_publication_enabled': False})['status'] == 'ok'
    assert probe.evaluate({**legacy, 'android_publication_enabled': True})['status'] == 'incident'
    assert not result['metrics']['android_executor_observed'] and not result['metrics']['android_reboot_verified']
    assert probe.evaluate({**value, 'windows_publication_enabled': 1})['status'] == 'incident'
    assert probe.evaluate(None)['status'] == 'unknown'
    assert probe.evaluate({**value, 'scheduler_worker_ok': False})['status'] == 'incident'
    assert probe.evaluate({key: val for key, val in value.items() if key != 'scheduler_available'})['status'] == 'unknown'


def test_zero_activity_is_not_an_incident():
    result = probe.evaluate({'control_center_mode': 'windows_bridge', 'windows_publication_enabled': True,
                            'android_publication_enabled': True, 'android_executor': 'whatsapp_images_pilot', 'status': 'ok', 'database_ok': True,
                            'jobs': 0, 'devices': 0, 'scheduler_available': True,
                            'scheduler_worker_ok': True, 'scheduler_tick_seconds': 10})
    assert result['status'] == 'ok' and result['business_mutations'] is False


def test_retry_health_is_not_a_phone_or_publication_proof():
    value = {'control_center_mode':'windows_bridge', 'windows_publication_enabled':True,
             'android_publication_enabled':True, 'android_executor':'whatsapp_images_pilot',
             'status':'ok', 'database_ok':True, 'scheduler_available':True,
             'scheduler_worker_ok':True, 'scheduler_tick_seconds':10,
             'manual_android_retry_available':True, 'publication_failure_stages':True}
    result = probe.evaluate(value)
    assert result['status'] == 'ok' and result['metrics']['manual_retry_contract_verified']
    assert result['metrics']['publication_verified'] is False
    assert probe.evaluate({**value,'publication_failure_stages':False})['status'] == 'incident'
    assert probe.evaluate({k:v for k,v in value.items() if k != 'manual_android_retry_available'})['status'] == 'incident'


def test_local_unlock_contract_does_not_claim_a_physical_unlock():
    value = {'control_center_mode':'windows_bridge', 'windows_publication_enabled':True,
             'android_publication_enabled':True, 'android_executor':'whatsapp_images_pilot',
             'status':'ok', 'database_ok':True, 'scheduler_available':True,
             'scheduler_worker_ok':True, 'scheduler_tick_seconds':10,
             'local_android_unlock_available':True, 'empty_status_review_available':True}
    result = probe.evaluate(value)
    assert result['status'] == 'ok' and result['metrics']['local_unlock_contract_verified']
    assert not result['metrics']['publication_verified']
    assert not result['metrics']['android_reboot_verified']
    assert probe.evaluate({**value,'empty_status_review_available':False})['status'] == 'incident'
