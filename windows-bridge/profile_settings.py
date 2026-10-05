"""Resolve private server settings only against already trusted local hardware."""
import json
from pathlib import Path
import subprocess


def available(root, adb, remote=None):
    local=json.loads((root/'config/profiles.json').read_text(encoding='utf-8-sig'))['profiles']
    inventory=subprocess.run([str(adb),'devices'],capture_output=True,text=True,check=True,timeout=15)
    connected={line.split()[0] for line in inventory.stdout.splitlines()[1:] if len(line.split())==2 and line.split()[1]=='device'}
    if remote is None:
        return {name:value for name,value in local.items() if value.get('enabled',True)
                and ({value.get('adb_serial'),value.get('device_id')} & connected)}
    result={}
    for setting in remote:
        if not setting.get('enabled',True):
            continue
        # Server settings cannot grant access to a new ADB identity or start a transport.
        base=local.get(setting['name'])
        serial=setting.get('adb_serial') or (base or {}).get('adb_serial')
        candidates=[value for value in local.values() if serial and value.get('adb_serial')==serial]
        if not candidates:
            continue
        base=base if base and base.get('adb_serial')==serial else candidates[0]
        target=serial if serial in connected else setting.get('device_id') or base.get('device_id')
        if target not in connected:
            continue
        if target != serial:
            identity=subprocess.run([str(adb),'-s',target,'shell','getprop','ro.serialno'],
                                    capture_output=True,text=True,timeout=15)
            if identity.returncode or identity.stdout.strip()!=serial:
                continue
        merged={**base,**setting,'device_id':target,'adb_serial':serial}
        if not setting.get('platform_version'):
            merged['platform_version']=base.get('platform_version','')
        for field in ('gallery','appium_overrides'):
            merged[field]={**base.get(field,{}),**{key:value for key,value in setting.get(field,{}).items() if value != ''}}
        result[setting['name']]=merged
    return result
