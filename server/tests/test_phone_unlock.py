"""Synthetic keyguard tests: no real devices, credentials, or publications."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

BRIDGE = Path(__file__).resolve().parents[2] / 'windows-bridge'
sys.path.insert(0, str(BRIDGE))
import phone_unlock as module

PIN = '1234'  # Synthetic only.
XML = '<hierarchy><node package="com.android.systemui" resource-id="com.android.systemui:id/pinEntry" />' + ''.join(
    f'<node package="com.android.systemui" resource-id="com.android.systemui:id/key{x}" text="{x}" />'
    for x in range(10)) + '</hierarchy>'


class Driver:
    page_source = XML
    def __init__(self): self.locked = True
    def is_locked(self): return self.locked
    def press_keycode(self, _code): pass
    def get_window_size(self): return {'width': 720, 'height': 1440}
    def swipe(self, *_args): pass


def test_secret_bound_to_local_profile_and_hardware(monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'read', lambda _path: {'schema': 1, 'pin': PIN,
                                                     'phones': {'Validation technique': 'SYNTHETIC001'}})
    assert module.load_pin(tmp_path, 'Validation technique', 'SYNTHETIC001') == PIN
    with pytest.raises(RuntimeError, match='SCOPE_REFUSED'):
        module.load_pin(tmp_path, 'Validation technique', 'UNKNOWN001')


def test_success_keeps_secret_out_of_argv_and_appium(monkeypatch, tmp_path):
    driver = Driver(); calls = []
    monkeypatch.setattr(module, 'load_pin', lambda *_args: PIN)
    def send(argv, **kwargs):
        calls.append((argv, kwargs)); driver.locked = False
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess, 'run', send)
    assert module.unlock(tmp_path, 'adb', 'SYNTHETIC001', 'Validation technique', driver,
                         lambda: None, pause=lambda _n: None)
    assert len(calls) == 1
    assert PIN not in repr(calls[0][0])
    assert PIN not in calls[0][1]['input']
    assert calls[0][0][-2:] == ['shell', '-T']
    assert calls[0][1]['input'].count('dumpsys window policy') == len(PIN) + 1
    assert not module.marker_for(tmp_path, 'SYNTHETIC001').exists()


def test_wrong_pin_and_crash_never_repeat_while_locked(monkeypatch, tmp_path):
    driver = Driver(); calls = []
    monkeypatch.setattr(module, 'load_pin', lambda *_args: PIN)
    monkeypatch.setattr(module.subprocess, 'run', lambda *_args, **_kwargs:
                        calls.append(1) or SimpleNamespace(returncode=0))
    for _ in range(2):
        assert not module.unlock(tmp_path, 'adb', 'SYNTHETIC001', 'Validation technique', driver,
                                 lambda: None, pause=lambda _n: None)
    assert len(calls) == 1
    driver.locked = False
    assert module.unlock(tmp_path, 'adb', 'SYNTHETIC001', 'Validation technique', driver, lambda: None)
    assert not module.marker_for(tmp_path, 'SYNTHETIC001').exists()


def test_never_types_into_app_or_after_cancellation(monkeypatch, tmp_path):
    driver = Driver()
    monkeypatch.setattr(module, 'load_pin', lambda *_args: pytest.fail('secret must not be loaded'))
    monkeypatch.setattr(module.subprocess, 'run', lambda *_args, **_kwargs: pytest.fail('must not type'))
    driver.page_source = XML.replace('com.android.systemui', 'com.example.app')
    assert not module.unlock(tmp_path, 'adb', 'SYNTHETIC001', 'Validation technique', driver,
                             lambda: None, pause=lambda _n: None)
    driver.page_source = XML
    def cancelled(): raise RuntimeError('AUTHORIZATION_REFUSED')
    assert not module.unlock(tmp_path, 'adb', 'SYNTHETIC001', 'Validation technique', driver, cancelled)


def test_tcp_transport_uses_trusted_hardware_scope(monkeypatch, tmp_path):
    driver = Driver(); scopes = []
    monkeypatch.setattr(module, 'load_pin', lambda _root, _profile, hardware: scopes.append(hardware) or PIN)
    monkeypatch.setattr(module.subprocess, 'run', lambda argv, **_kwargs:
                        setattr(driver, 'locked', False) or SimpleNamespace(returncode=0))
    assert module.unlock(tmp_path, 'adb', '192.0.2.1:5555', 'Validation technique', driver,
                         lambda: None, pause=lambda _n: None, hardware='SYNTHETIC001')
    assert scopes == ['SYNTHETIC001']


def test_partial_or_ambiguous_pin_field_is_refused():
    assert module.pin_keyguard(XML)
    assert not module.pin_keyguard(XML.replace('id/pinEntry" />', 'id/pinEntry" text="••" />'))
    extra = '<node package="com.android.systemui" resource-id="com.android.systemui:id/pinEntry" />'
    assert not module.pin_keyguard(XML.replace('</hierarchy>', extra + '</hierarchy>'))
