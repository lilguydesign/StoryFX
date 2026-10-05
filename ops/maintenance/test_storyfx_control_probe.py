"""Missing evidence must not be promoted to publication or endurance success."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('control_probe', Path(__file__).with_name('storyfx_control_probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_contract_and_private_boundary():
    value = {'control_center_mode': 'windows_bridge', 'windows_publication_enabled': True,
             'android_publication_enabled': False, 'status': 'ok', 'database_ok': True}
    result = probe.evaluate(value)
    assert result['status'] == 'ok'
    assert result['metrics']['publication_verified'] is False
    assert result['metrics']['windows_executor_observed'] is False
    assert probe.evaluate({**value, 'android_publication_enabled': True})['status'] == 'incident'
    assert probe.evaluate({**value, 'windows_publication_enabled': 1})['status'] == 'incident'
    assert probe.evaluate(None)['status'] == 'unknown'


def test_zero_activity_is_not_an_incident():
    result = probe.evaluate({'control_center_mode': 'windows_bridge', 'windows_publication_enabled': True,
                            'android_publication_enabled': False, 'status': 'ok', 'database_ok': True,
                            'jobs': 0, 'devices': 0})
    assert result['status'] == 'ok' and result['business_mutations'] is False
