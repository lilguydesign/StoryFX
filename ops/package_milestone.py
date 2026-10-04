"""Package only committed foundation files and explicit safe local deliverables."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ('server/', 'dashboard/', 'android-agent/', 'docs/internet/', 'ops/', '.github/workflows/')
SINGLES = {'.gitignore', 'README.md', 'README.internet.md', 'Start_StoryFX_Diagnostic.ps1'}
SECRET = re.compile(rb'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|'
                    rb'eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}|'
                    rb'gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}')


def git(*args):
    result = subprocess.run(['git', '-c', 'safe.directory=' + str(ROOT), '-C', str(ROOT), *args],
                            capture_output=True, check=True)
    return result.stdout


def package(apk, base):
    delivery = ROOT / 'delivery'
    delivery.mkdir(exist_ok=True)
    changed = git('diff', '--name-only', base + '...HEAD').decode().splitlines()
    payload, inventory = {}, []
    for name in changed:
        if name not in SINGLES and not name.startswith(PREFIXES):
            raise ValueError('PACKAGE_SCOPE_MISMATCH')
        if any(part in {'.runtime', 'transmission', 'build', '.gradle', '.venv'} for part in Path(name).parts):
            raise ValueError('PRIVATE_OR_GENERATED_PATH')
        blob = git('show', 'HEAD:' + name)
        if SECRET.search(blob):
            raise ValueError('SECRET_PATTERN_FOUND: ' + name)
        if Path(name).suffix in {'.py', '.kt', '.kts', '.js', '.css', '.html', '.sql', '.ps1', '.yml'}:
            lines = len(blob.splitlines())
            if lines > 300:
                raise ValueError('SOURCE_TOO_LONG: ' + name)
            try:
                before = len(git('show', base + ':' + name).splitlines())
            except subprocess.CalledProcessError:
                before = 0
            inventory.append({'path': name, 'line_count_before': before, 'line_count_after': lines})
        payload['source/' + name] = blob
    for name in ('FINAL_REPORT.txt', 'dashboard-demo.png', 'dashboard-demo-light.png',
                 'dashboard-demo-mobile.png', 'android-agent.png', 'android-e2e.json', 'dashboard-ui-check.json'):
        path = delivery / name
        if path.is_file():
            blob = path.read_bytes()
            if path.suffix in {'.txt', '.json'} and SECRET.search(blob):
                raise ValueError('PRIVATE_REPORT_PATTERN_FOUND')
            payload['evidence/' + name] = blob
    if apk is not None:
        path = Path(apk).resolve(strict=True)
        if not path.is_relative_to(ROOT / 'android-agent' / 'app' / 'build' / 'outputs' / 'apk'):
            raise ValueError('APK_SCOPE_MISMATCH')
        payload['android/StoryFX-Agent-0.1.0-debug.apk'] = path.read_bytes()
    manifest = [{'path': name, 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}
                for name, blob in sorted(payload.items())]
    payload['MANIFEST.json'] = json.dumps(manifest, indent=2).encode()
    payload['LINE_COUNTS.json'] = json.dumps(inventory, indent=2).encode()
    (delivery / 'LINE_COUNTS.json').write_bytes(payload['LINE_COUNTS.json'])
    destination = delivery / 'StoryFX_Jalon1_20261004.zip'
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, blob in payload.items():
            archive.writestr(name, blob)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP_INTEGRITY_FAILED')
        for entry in manifest:
            actual = hashlib.sha256(archive.read(entry['path'])).hexdigest()
            if actual != entry['sha256']:
                raise ValueError('ZIP_MANIFEST_MISMATCH')
    print(json.dumps({'artifact': str(destination), 'bytes': destination.stat().st_size,
                      'files': len(payload), 'integrity': 'verified', 'scope': 'committed_foundation_only'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apk')
    parser.add_argument('--base', default='origin/main')
    args = parser.parse_args()
    package(args.apk, args.base)
