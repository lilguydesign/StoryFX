"""CI-only witness: admin-off Caddy applies and rolls back without restarting."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


CONTAINER = 'storyfx-ci-caddy'
IMAGE = 'caddy:2.11.3-alpine'
COMMAND = ['caddy', 'run', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile']
HTTP = build_opener(ProxyHandler({}))


def docker(*args):
    return subprocess.run(['docker', *args], text=True, capture_output=True, check=True)


def source(body):
    return '{\n    admin off\n    auto_https off\n}\nhttp://:8080 {\n    respond "' + body + '"\n}\n'


def started_at():
    return docker('inspect', '--format', '{{.State.StartedAt}}', CONTAINER).stdout.strip()


def wait_response(url, expected):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with HTTP.open(url, timeout=1) as response:
                if response.status == 200 and response.read().decode() == expected:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.15)
    raise RuntimeError('CADDY_RELOAD_HTTP_WITNESS_FAILED')


def installer():
    path = Path(__file__).resolve().parents[1] / 'deploy' / 'install_https.py'
    spec = importlib.util.spec_from_file_location('storyfx_https_installer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CONTAINER = CONTAINER
    return module


def main():
    if os.environ.get('CI') != 'true':
        raise RuntimeError('CADDY_RELOAD_TEST_CI_ONLY')
    existing = subprocess.run(['docker', 'inspect', CONTAINER], capture_output=True)
    if existing.returncode == 0:
        raise RuntimeError('EXISTING_CADDY_TEST_CONTAINER_REFUSED')
    module = installer()
    owned = ''
    with tempfile.TemporaryDirectory(prefix='storyfx-caddy-ci-') as folder:
        config = Path(folder) / 'Caddyfile'
        config.write_text(source('old'), encoding='utf-8')
        try:
            owned = docker('create', '--name', CONTAINER,
                           '--publish', '127.0.0.1::8080',
                           '--mount', f'type=bind,src={folder},dst=/etc/caddy,readonly',
                           '--tmpfs', '/data', '--tmpfs', '/config', '--read-only',
                           '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                           IMAGE, *COMMAND).stdout.strip()
            if not re.fullmatch(r'[a-f0-9]{64}', owned):
                raise RuntimeError('CADDY_TEST_CONTAINER_ID_REFUSED')
            docker('start', owned)
            ports = json.loads(docker('inspect', '--format',
                                    '{{json .NetworkSettings.Ports}}', owned).stdout)
            binding = ports['8080/tcp']
            if len(binding) != 1 or binding[0]['HostIp'] != '127.0.0.1':
                raise RuntimeError('CADDY_TEST_LOOPBACK_BINDING_REFUSED')
            url = 'http://127.0.0.1:' + binding[0]['HostPort'] + '/'
            wait_response(url, 'old')
            original_start = started_at()
            config.write_text(source('new'), encoding='utf-8')
            module.reload_gateway(source('new'))
            wait_response(url, 'new')
            assert started_at() == original_start, 'CADDY_RESTART_DURING_RELOAD'
            config.write_text(source('old'), encoding='utf-8')
            module.reload_gateway(source('old'))
            wait_response(url, 'old')
            assert started_at() == original_start, 'CADDY_RESTART_DURING_ROLLBACK'
            print(json.dumps({'caddy_admin_off_reload': 'passed',
                              'http_transition': ['old', 'new', 'old'],
                              'container_started_at_unchanged': True}))
        finally:
            if re.fullmatch(r'[a-f0-9]{64}', owned):
                docker('rm', '--force', owned)


if __name__ == '__main__':
    main()
