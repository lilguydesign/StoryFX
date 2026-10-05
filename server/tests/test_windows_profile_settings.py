"""Cloud metadata does not grant ADB access to new hardware or open transports."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

spec=importlib.util.spec_from_file_location('profile_settings',Path(__file__).resolve().parents[2]/'windows-bridge/profile_settings.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_known_usb_binding_alias_and_new_hardware_refusal(tmp_path,monkeypatch):
    folder=tmp_path/'config';folder.mkdir()
    (folder/'profiles.json').write_text(json.dumps({'profiles':{'Validation technique':{'adb_serial':'SYNTHETIC001','device_id':'192.0.2.1:5555','platform_version':'16'}}}))
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout='List of devices attached\nSYNTHETIC001\tdevice\n')
    monkeypatch.setattr(module.subprocess,'run',run)
    remote=[{'name':'Validation technique alias','adb_serial':'SYNTHETIC001','enabled':True,'offset_minutes':42},
            {'name':'Validation technique inconnue','adb_serial':'SYNTHETIC002','enabled':True}]
    result=module.available(tmp_path,Path('synthetic-adb'),remote)
    assert list(result)==['Validation technique alias']
    assert result['Validation technique alias']['device_id']=='SYNTHETIC001'
    assert result['Validation technique alias']['offset_minutes']==42
    assert len(calls)==1 and 'connect' not in calls[0]


def test_wifi_binding_must_report_the_trusted_hardware_identity(tmp_path,monkeypatch):
    folder=tmp_path/'config';folder.mkdir()
    (folder/'profiles.json').write_text(json.dumps({'profiles':{'Validation technique':{'adb_serial':'SYNTHETIC001','device_id':'192.0.2.1:5555'}}}))
    def run(args,**kwargs):
        return SimpleNamespace(returncode=0,stdout='List of devices attached\n192.0.2.3:5555\tdevice\n' if args[-1]=='devices' else 'SYNTHETIC002\n')
    monkeypatch.setattr(module.subprocess,'run',run)
    assert not module.available(tmp_path,Path('synthetic-adb'),[{'name':'Validation technique','adb_serial':'SYNTHETIC001','device_id':'192.0.2.3:5555'}])
