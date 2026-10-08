"""Exercise the real installer with isolated paths and inert command stubs."""
import os
from pathlib import Path
import subprocess
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux deployment contract')
SOURCE = Path(__file__).resolve().parents[2] / 'deploy' / 'install_backend.sh'
COMMIT = 'b' * 40
IMAGE = 'sha256:' + 'c' * 64


def run_installer(tmp_path, expected, *, healthy=True):
    root, bundle, commands = (tmp_path / name for name in ('service', 'bundle', 'commands'))
    for folder in (root, bundle / 'deploy', commands):
        folder.mkdir(parents=True)
    (bundle / 'deploy' / 'Dockerfile').write_text('FROM scratch\n')
    previous = root / 'releases' / ('a' * 40)
    previous.mkdir(parents=True)
    (root / 'current').symlink_to(previous, target_is_directory=True)
    log = tmp_path / 'commands.log'
    stubs = {
        'hostname': 'printf "%s\\n" formafx-prod-db-02',
        'docker': '''printf '%s\n' "$*" >> "$STORYFX_TEST_LOG"
if [[ "$1 $2" == 'image inspect' ]]; then printf '%s\n' "$STORYFX_TEST_IMAGE"; fi''',
        'python3': '''if [[ "$1" == '-' && "$2" == */health.json && ! -s "$2" ]]; then exit 1; fi
exit 0''',
        'curl': '''printf 'health\n' >> "$STORYFX_TEST_LOG"
[[ "$STORYFX_TEST_HEALTH" == 1 ]] || exit 22
printf '{"mode":"diagnostic_only","publishing_enabled":false,"account_auth_enabled":true}' ''',
        'sleep': 'exit 0',
    }
    for name, content in stubs.items():
        script = commands / name
        script.write_text('#!/bin/bash\n' + content + '\n')
        script.chmod(0o700)
    source = SOURCE.read_text()
    assert source.count('ROOT=/opt/formafx/storyfx') == 1
    assert source.count('[[ "$BUNDLE" == /tmp/storyfx-release-* ]]') == 1
    source = source.replace('ROOT=/opt/formafx/storyfx', 'ROOT=' + str(root))
    source = source.replace('[[ "$BUNDLE" == /tmp/storyfx-release-* ]]', '[[ "$BUNDLE" == ' + str(bundle) + ' ]]')
    installer = tmp_path / 'install.sh'
    installer.write_text(source)
    env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ['PATH'],
               STORYFX_TEST_LOG=str(log), STORYFX_TEST_IMAGE=IMAGE, STORYFX_TEST_HEALTH=str(int(healthy)))
    result = subprocess.run(['bash', str(installer), str(bundle), COMMIT, expected],
                            env=env, capture_output=True, text=True, timeout=15)
    return result, log.read_text() if log.exists() else '', root, previous


def test_verified_prebuilt_image_skips_build_and_retains_rollback(tmp_path):
    result, calls, root, previous = run_installer(tmp_path, IMAGE)
    assert result.returncode == 0, result.stderr
    assert 'build ' not in calls and 'image inspect ' in calls
    assert 'stop storyfx-api' in calls and 'compose ' in calls
    assert (root / 'current').resolve().name == COMMIT
    assert 'rollback=' + str(previous) in result.stdout


def test_prebuilt_mismatch_preserves_previous_release_without_stopping(tmp_path):
    result, calls, root, previous = run_installer(tmp_path, 'sha256:' + 'd' * 64)
    assert result.returncode != 0
    assert 'build ' not in calls and 'stop storyfx-api' not in calls
    assert (root / 'current').resolve() == previous
    assert 'backend_install=failed_rolled_back' in result.stdout


def test_invalid_image_identity_exits_before_any_docker_command(tmp_path):
    result, calls, root, previous = run_installer(tmp_path, 'unverified-image')
    assert result.returncode == 25 and not calls
    assert (root / 'current').resolve() == previous


def test_health_failure_is_bounded_and_restores_previous_release(tmp_path):
    result, calls, root, previous = run_installer(tmp_path, IMAGE, healthy=False)
    assert result.returncode != 0
    assert calls.splitlines().count('health') == 15
    assert 'stop storyfx-api' in calls
    assert (root / 'current').resolve() == previous
    assert 'backend_install=failed_rolled_back' in result.stdout


def test_default_installer_still_builds_when_no_image_identity_is_given(tmp_path):
    result, calls, root, _ = run_installer(tmp_path, '')
    assert result.returncode == 0
    assert 'build --pull ' in calls and 'image inspect ' not in calls
    assert (root / 'current').resolve().name == COMMIT
