"""Add one read-only StoryFX check to the current collector, preserving other work."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import uuid

BASE = Path('/opt/formafx/fx-maintenance')
FILES = {'storyfx_control_probe.py', 'storyfx_control_catalog.json', 'install_control_probe.py'}
IMPORT = 'from storyfx_control_probe import collect as collect_storyfx_control'
CALL = '    checks.append(collect_storyfx_control())'


def patch(text):
    if IMPORT in text and CALL in text:
        return text
    if IMPORT in text or CALL in text:
        raise RuntimeError('PARTIAL_CONTROL_INTEGRATION')
    anchor = 'from storyfx_public_probe import collect_storyfx_public_checks'
    invocation = '    checks.extend(collect_storyfx_public_checks(now=now))'
    if text.count(anchor) != 1 or text.count(invocation) != 1:
        raise RuntimeError('CONTROL_ANCHOR_CHANGED')
    changed = text.replace(anchor, anchor + '\n' + IMPORT).replace(invocation, invocation + '\n' + CALL)
    ast.parse(changed)
    assert changed.replace('\n' + IMPORT, '').replace('\n' + CALL, '') == text
    return changed


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(file.relative_to(folder)): sha(file) for file in folder.rglob('*')
            if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc'}


def command(code, args, timeout=60):
    result = subprocess.run(args, cwd=code, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('CONTROL_MAINTENANCE_GATE_FAILED')
    return result.stdout


def install(archive, expected_sha, commit, expected_collector):
    assert re.fullmatch('[a-f0-9]{40}', commit)
    assert re.fullmatch('[a-f0-9]{64}', expected_sha) and re.fullmatch('[a-f0-9]{64}', expected_collector)
    assert str(Path(archive).resolve()).startswith('/tmp/storyfx-control-maintenance-')
    assert command(BASE, ['hostname']).strip() == 'formafx-prod-db-02'
    assert sha(Path(archive)) == expected_sha
    current = (BASE / 'current').resolve(strict=True)
    assert current.is_relative_to(BASE / 'releases') and sha(current / 'collector.py') == expected_collector
    before = inventory(current)
    collector = patch((current / 'collector.py').read_text())
    code = BASE / 'releases' / ('storyfx-control-' + commit) / 'ops' / 'fx-maintenance'
    assert not code.exists(), 'IMMUTABLE_MAINTENANCE_RELEASE_EXISTS'
    with tarfile.open(archive) as source:
        members = source.getmembers()
        assert {member.name for member in members} == FILES and len(members) == len(FILES)
        assert all(member.isfile() and member.size < 65536 for member in members)
        shutil.copytree(current, code, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for member in members:
            (code / member.name).write_bytes(source.extractfile(member).read())
    for name, digest in before.items():
        if name not in FILES:
            assert sha(code / name) == digest
    (code / 'collector.py').write_text(collector)
    for name in ('collector.py', 'storyfx_control_probe.py', 'install_control_probe.py'):
        compile((code / name).read_text(), name, 'exec')
    command(code, ['/usr/bin/python3', '-B', '-m', 'unittest', 'test_notification_policy',
                   'test_state_durability', 'test_service_window'])
    proof = json.loads(command(code, ['/usr/bin/python3', '-B', 'storyfx_control_probe.py']))
    assert proof['status'] == 'ok' and proof['notifications_sent'] is False
    sys.path.insert(0, str(code))
    from deployment_health import validate_collection
    snapshot = validate_collection(command(code, ['/usr/bin/python3', '-B', 'run.py', '--check-only'], 120))
    checks = {row['id']: row for row in snapshot['checks']}
    assert all(checks[key]['status'] == 'ok' for key in
               ('storyfx_control_plane', 'storyfx_public_health', 'storyfx_agent_latest'))
    assert (BASE / 'current').resolve(strict=True) == current and inventory(current) == before
    assert sha(code / 'notification_policy.py') == before['notification_policy.py']
    receipt = {'installed': True, 'commit': commit, 'previous_release': str(current),
               'new_release': str(code), 'preserved_files': len(before),
               'checks': [checks[key] for key in checks if key.startswith('storyfx_')],
               'notifications_sent': False, 'timers_modified': False, 'quota_preserved': True,
               'private_executor_verified': False, 'publication_replayed': False}
    (code.parent.parent / 'deployment.json').write_text(json.dumps(receipt))
    temporary = BASE / ('current.storyfx-control-' + uuid.uuid4().hex)
    temporary.symlink_to(code, target_is_directory=True)
    os.replace(temporary, BASE / 'current')
    print(json.dumps(receipt))


if __name__ == '__main__':
    try:
        install(*sys.argv[1:])
    except Exception as error:
        print(json.dumps({'installed': False, 'error_kind': type(error).__name__,
                          'notifications_sent': False, 'current_preserved_on_failure': True}))
        raise SystemExit(1)
