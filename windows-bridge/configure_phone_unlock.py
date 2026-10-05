"""Migrate the existing private legacy PIN to CurrentUser DPAPI, never to the server."""
import argparse
import ast
import getpass
import json
from pathlib import Path
import re
import subprocess

from secure_state import read, save

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ('JK650_S23', 'JK657_S23+')


def legacy_pin():
    tree = ast.parse((ROOT / 'engine/core.py').read_text(encoding='utf-8-sig'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'unlock_screen_if_needed')
    values = [n.value.value for n in ast.walk(function) if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'PASSWORD' for t in n.targets)
              and isinstance(n.value, ast.Constant)]
    if len(values) != 1:
        raise RuntimeError('LEGACY_PIN_UNAVAILABLE')
    return values[0]


def configure(import_legacy=False):
    path = ROOT / '.runtime/windows-bridge/phone-unlock.dpapi'
    if path.exists():
        read(path)
        return {'configured': True, 'existing_secret_preserved': True}
    profiles = json.loads((ROOT / 'config/profiles.json').read_text(encoding='utf-8-sig'))['profiles']
    phones = {name: profiles[name]['adb_serial'] for name in TARGETS}
    if any(not serial for serial in phones.values()):
        raise RuntimeError('TRUSTED_PHONE_REQUIRED')
    pin = legacy_pin() if import_legacy else getpass.getpass('Code des deux téléphones (masqué) : ')
    if not isinstance(pin, str) or not re.fullmatch(r'\d{4,16}', pin, flags=re.ASCII):
        raise RuntimeError('PIN_FORMAT_REFUSED')
    save(path, {'schema': 1, 'phones': phones, 'pin': pin})
    pin = None
    # DPAPI encryption plus CurrentUser/SYSTEM file access, no inherited readers.
    account = subprocess.check_output(['whoami'], text=True).strip()
    result = subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                             account + ':F', '*S-1-5-18:F'], capture_output=True)
    if result.returncode:
        raise RuntimeError('PRIVATE_STATE_ACL_REFUSED')
    read(path)
    return {'configured': True, 'encrypted': True, 'trusted_phone_count': len(phones),
            'secret_logged': False, 'cloud_secret_uploaded': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--import-legacy', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(configure(args.import_legacy)))
    except Exception:
        raise SystemExit('Configuration privée indisponible. Aucun code affiché.')
