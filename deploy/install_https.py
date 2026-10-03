"""Add only StoryFX's site to the verified host-network Caddy gateway."""
import json
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime, timezone

PATH = Path('/opt/formafx/public-api-caddy/Caddyfile')
CONTAINER = 'formafx-public-api-caddy'
MARKER = '# StoryFX private pilot managed site'
BLOCK = '\n' + MARKER + '\nstory.formafx.com {\n  reverse_proxy 127.0.0.1:18451\n}\n'


def run(*args):
    return subprocess.run(args, text=True, capture_output=True, check=True)


def main():
    assert run('hostname').stdout.strip() == 'formafx-prod-db-02'
    inspect = json.loads(run('docker', 'inspect', '--format', '{{json .HostConfig.NetworkMode}}', CONTAINER).stdout)
    assert inspect == 'host'
    source = PATH.read_text()
    if re.search(r'(?m)^story\.formafx\.com\s*\{', source):
        assert BLOCK.strip() in source, 'EXISTING_STORY_CONFIGURATION_DIFFERS'
        print('https_config=already_current')
        return
    backup = Path('/opt/formafx/storyfx/backups') / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_https')
    backup.mkdir(mode=0o700)
    shutil.copy2(PATH, backup / 'Caddyfile')
    candidate = PATH.with_name('Caddyfile.storyfx-candidate')
    candidate.write_text(source.rstrip() + '\n' + BLOCK)
    try:
        run('docker', 'cp', str(candidate), CONTAINER + ':/tmp/storyfx-caddy-candidate')
        run('docker', 'exec', CONTAINER, 'caddy', 'validate', '--config', '/tmp/storyfx-caddy-candidate', '--adapter', 'caddyfile')
        PATH.write_text(candidate.read_text())
        run('docker', 'exec', CONTAINER, 'caddy', 'reload', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile')
    except Exception:
        shutil.copy2(backup / 'Caddyfile', PATH)
        run('docker', 'exec', CONTAINER, 'caddy', 'reload', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile')
        raise RuntimeError('HTTPS_CONFIGURATION_ROLLED_BACK') from None
    finally:
        candidate.unlink(missing_ok=True)
    print('https_config=installed\nbackup=' + str(backup))


if __name__ == '__main__':
    main()
