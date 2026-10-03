"""Build a deployment archive from one committed tree, never the dirty checkout."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ('server/storyfx_server/', 'dashboard/', 'deploy/', 'supabase/')
FILES = ('server/requirements-lock.txt',)


def main(commit):
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('EXACT_COMMIT_REQUIRED')
    destination = ROOT / '.runtime' / 'deploy' / commit
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / 'storyfx-release.tar'
    subprocess.run(['git', '-c', 'safe.directory=' + str(ROOT), '-c', 'core.autocrlf=false',
                    '-c', 'core.eol=lf', 'archive', '--format=tar', '--output', str(archive), commit,
                    'server/storyfx_server', 'server/requirements-lock.txt', 'dashboard', 'deploy', 'supabase'],
                   cwd=ROOT, check=True)
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            if not member.isfile():
                continue
            if member.name not in FILES and not member.name.startswith(PREFIXES):
                raise ValueError('BUNDLE_SCOPE_REFUSED')
            if any(part in {'.env', '.secrets', 'env.web', 'session.key'} for part in Path(member.name).parts):
                raise ValueError('PRIVATE_FILE_REFUSED')
            if member.name.endswith('.sh') and b'\r\n' in source.extractfile(member).read():
                raise ValueError('LINUX_SCRIPT_CRLF_REFUSED')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = {'commit': commit, 'archive': archive.name, 'sha256': digest}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest))
    print('artifact=' + str(archive))


if __name__ == '__main__':
    main(sys.argv[1])
