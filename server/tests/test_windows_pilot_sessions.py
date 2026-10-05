"""Two dedicated pilot sessions may coexist without resetting the historical one."""
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import pytest

spec=importlib.util.spec_from_file_location('publication_adapter',Path(__file__).resolve().parents[2]/'windows-bridge/publication_adapter.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def fake_appium(monkeypatch):
    class Options:
        def load_capabilities(self,value):
            self.value=value;return self
    class Remote:
        def __init__(self,url,options):
            self.start_session(options.value)
        def start_session(self,value):
            self.caps=value;self.session_id='new-validation-session'
    app=ModuleType('appium');app.webdriver=SimpleNamespace(Remote=Remote)
    android=ModuleType('appium.options.android');android.UiAutomator2Options=Options
    monkeypatch.setitem(sys.modules,'appium',app)
    monkeypatch.setitem(sys.modules,'appium.options.android',android)
    monkeypatch.setattr(module,'ensure_pilot_server',lambda:None)


def test_second_phone_uses_distinct_port_and_first_session_is_borrowed(monkeypatch):
    fake_appium(monkeypatch)
    first={'id':'first-validation-session','capabilities':{'appium:udid':'SYNTHETIC001','appium:systemPort':8201}}
    monkeypatch.setattr(module,'sessions',lambda url:[] if '4723' in url else [first])
    second=module.driver_for('SYNTHETIC002')
    assert second.caps['appium:systemPort']==8202
    borrowed=module.driver_for('SYNTHETIC001')
    assert borrowed.session_id==first['id']
    assert first['capabilities']['appium:systemPort']==8201


def test_busy_historical_controller_and_port_collision_are_refused(monkeypatch):
    fake_appium(monkeypatch)
    monkeypatch.setattr(module,'sessions',lambda url:[{'id':'validation-controller'}])
    with pytest.raises(RuntimeError,match='EXISTING_APPIUM_CONTROLLER_BUSY'):
        module.driver_for('SYNTHETIC001')
    monkeypatch.setattr(module,'sessions',lambda url:[] if '4723' in url else
                        [{'id':'validation','capabilities':{'appium:udid':'SYNTHETIC001','appium:systemPort':8201}}])
    with pytest.raises(RuntimeError,match='PILOT_APPIUM_PORT_COLLISION'):
        module.driver_for('SYNTHETIC002',{'appium_overrides':{'systemPort':8201}})
