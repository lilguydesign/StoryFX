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
DOWNLOAD_BLOCK = '''    # StoryFX immutable Android downloads
    handle_path /downloads/storyfx-android/* {
        root * /data/downloads/storyfx-android
        header Cache-Control "public, max-age=31536000, immutable"
        header X-Content-Type-Options "nosniff"
        file_server
    }
'''


def run(*args):
    return subprocess.run(args, text=True, capture_output=True, check=True)


def main():
    assert run('hostname').stdout.strip() == 'formafx-prod-db-02'
    inspect = json.loads(run('docker', 'inspect', '--format', '{{json .HostConfig.NetworkMode}}', CONTAINER).stdout)
    assert inspect == 'host'
    source = PATH.read_text()
    site_exists = bool(re.search(r'(?m)^story\.formafx\.com\s*\{', source))
    if site_exists:
        assert BLOCK.strip() in source, 'EXISTING_STORY_CONFIGURATION_DIFFERS'
    download_exists = '/downloads/storyfx-android/' in source
    if download_exists:
        assert DOWNLOAD_BLOCK.strip() in source, 'EXISTING_DOWNLOAD_CONFIGURATION_DIFFERS'
    if site_exists and download_exists:
        print('https_config=already_current')
        return
    updated = source
    if not download_exists:
        anchor = '    handle_path /downloads/remotefx-agent/* {'
        assert updated.count(anchor) == 1, 'API_DOWNLOAD_INSERTION_TARGET_REFUSED'
        updated = updated.replace(anchor, DOWNLOAD_BLOCK + '\n' + anchor, 1)
    if not site_exists:
        updated = updated.rstrip() + '\n' + BLOCK
    backup = Path('/opt/formafx/storyfx/backups') / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_https')
    backup.mkdir(mode=0o700)
    shutil.copy2(PATH, backup / 'Caddyfile')
    candidate = PATH.with_name('Caddyfile.storyfx-candidate')
    candidate.write_text(updated)
    applied = False
    try:
        run('docker', 'cp', str(candidate), CONTAINER + ':/tmp/storyfx-caddy-candidate')
        run('docker', 'exec', CONTAINER, 'caddy', 'validate', '--config', '/tmp/storyfx-caddy-candidate', '--adapter', 'caddyfile')
        assert PATH.read_text() == source, 'CONCURRENT_CADDY_CHANGE_REFUSED'
        PATH.write_text(candidate.read_text())
        applied = True
        run('docker', 'exec', CONTAINER, 'caddy', 'reload', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile')
    except Exception:
        if applied:
            if PATH.read_text() != updated:
                raise RuntimeError('CONCURRENT_CADDY_CHANGE_MANUAL_ROLLBACK_REQUIRED') from None
            shutil.copy2(backup / 'Caddyfile', PATH)
            run('docker', 'exec', CONTAINER, 'caddy', 'reload', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile')
            raise RuntimeError('HTTPS_CONFIGURATION_ROLLED_BACK') from None
        raise RuntimeError('HTTPS_CONFIGURATION_NOT_MODIFIED') from None
    finally:
        candidate.unlink(missing_ok=True)
    print('https_config=installed\nbackup=' + str(backup))


if __name__ == '__main__':
    main()
