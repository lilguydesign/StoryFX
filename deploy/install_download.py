"""Publish the immutable signed APK, verify public bytes, then advance latest."""
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

FUNCTIONS = Path('/opt/formafx/supabase-staging/current/volumes/functions')
EDGE = 'formafx-staging-supabase-edge-functions'
DB = 'formafx-staging-supabase-db'
NAME = 'StoryFX-Android-0.2.0-v2.apk'
SHA = 'f3f7b41ae165344bd405b0698a35e63fe08d6d73325b454cae54812df3db80e5'
SIZE = 1729354
URL = 'https://api.formafx.com/downloads/storyfx-android/' + NAME
VERSION, CODE = '0.2.0', 2


def configure(manifest):
    global NAME, SHA, SIZE, URL, VERSION, CODE
    value = json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
    version, code = value['version'], value['version_code']
    assert isinstance(version, str) and re.fullmatch(r'\d+\.\d+\.\d+', version)
    assert type(code) is int and 0 < code < 2147483647
    assert re.fullmatch(r'[a-f0-9]{64}', value['sha256'])
    assert type(value['bytes']) is int and 0 < value['bytes'] <= 134217728
    assert value['package'] == 'com.formafx.storyfx.agent'
    assert value['certificate_sha256'] == 'e3795a1bca6acab02ce61b724ef827c35c19a2c4ffbbb7d9c4c3af3fa7009a12'
    assert value['apk_signature_verified'] is True and value['release_identity_verified'] is True
    VERSION, CODE, SHA, SIZE = version, code, value['sha256'], value['bytes']
    NAME = f'StoryFX-Android-{VERSION}-v{CODE}.apk'
    URL = 'https://api.formafx.com/downloads/storyfx-android/' + NAME


def run(*args, **kwargs):
    return subprocess.run(args, capture_output=True, check=True, **kwargs)


def sql(text):
    return run('docker', 'exec', '-i', DB, 'psql', '-X', '-U', 'postgres', '-d', 'postgres',
               '-A', '-t', '-v', 'ON_ERROR_STOP=1', input=text.encode()).stdout


def check_public():
    with urllib.request.urlopen(URL, timeout=30) as response:
        content = response.read(SIZE + 1)
        assert response.status == 200
        assert 'text/html' not in response.headers.get('Content-Type', '')
    assert len(content) == SIZE and hashlib.sha256(content).hexdigest() == SHA


def verify_metadata(metadata_url, opener=urllib.request.urlopen, pause=time.sleep):
    for attempt in range(6):
        try:
            with opener(metadata_url, timeout=10) as response:
                metadata = json.load(response)
            assert metadata['ok'] is True and metadata['sha256'] == SHA, 'METADATA_HASH_REFUSED'
            assert metadata['download_url'] == URL, 'METADATA_URL_REFUSED'
            assert metadata['publishing_enabled'] is False, 'METADATA_MODE_REFUSED'
            return
        except urllib.error.HTTPError as error:
            if error.code not in {502, 503, 504} or attempt == 5:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 5:
                raise
        pause(1)


def main(bundle):
    bundle = Path(bundle).resolve()
    assert str(bundle).startswith('/tmp/storyfx-release-')
    assert run('hostname').stdout.strip() == b'formafx-prod-db-02'
    assert Path('/tmp/' + NAME).stat().st_size == SIZE
    assert hashlib.sha256(Path('/tmp/' + NAME).read_bytes()).hexdigest() == SHA
    backup = Path('/opt/formafx/storyfx/backups') / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_download')
    backup.mkdir(mode=0o700, parents=True)
    before = sql("SELECT row_to_json(v) FROM public.app_versions v WHERE platform='storyfx_agent_android';").decode().strip()
    previous = json.loads(before) if before else None
    (backup / 'app-version-before.json').write_text(json.dumps(previous))
    target = FUNCTIONS / 'storyfx-agent-download'
    existed = target.exists()
    sources = list((bundle / 'supabase/functions/storyfx-agent-download').iterdir())
    changed = any(not (target / source.name).is_file() or source.read_bytes() != (target / source.name).read_bytes()
                  for source in sources)
    reload_needed = existed and changed
    if existed:
        shutil.copytree(target, backup / 'storyfx-agent-download')
    assets = Path('/opt/formafx/public-api-caddy/data/downloads/storyfx-android')
    assets.mkdir(parents=True, exist_ok=True)
    apk = assets / NAME
    if apk.exists():
        assert hashlib.sha256(apk.read_bytes()).hexdigest() == SHA, 'IMMUTABLE_APK_DIFFERS'
    else:
        shutil.copyfile('/tmp/' + NAME, apk)
    apk.chmod(0o644)
    check_public()
    sql((bundle / 'supabase/migrations/20261003_01_storyfx_release_catalog.sql').read_text())
    committed = False
    phase = 'function_installation'
    try:
        target.mkdir(exist_ok=True)
        for source in sources:
            assert source.is_file() and source.suffix in {'.ts', '.toml'}
            temporary = target / (source.name + '.storyfx-tmp')
            shutil.copyfile(source, temporary)
            temporary.chmod(0o644)
            temporary.replace(target / source.name)
        if reload_needed:
            run('docker', 'restart', EDGE)
        statement = f"""BEGIN;
        INSERT INTO public.storyfx_android_releases(version,version_code,download_url,sha256,byte_size)
        VALUES('{VERSION}',{CODE},'{URL}','{SHA}',{SIZE}) ON CONFLICT(version) DO NOTHING;
        DO $verify$ BEGIN
          IF NOT EXISTS(SELECT 1 FROM public.storyfx_android_releases WHERE version='{VERSION}'
            AND version_code={CODE} AND sha256='{SHA}' AND byte_size={SIZE} AND download_url='{URL}')
          THEN RAISE EXCEPTION 'IMMUTABLE_CATALOG_DIFFERS'; END IF;
        END $verify$;
        UPDATE public.app_versions SET latest_version='{VERSION}',
          download_url='{URL}',sha256='{SHA}',publish_date=now(),updated_at=now()
          WHERE platform='storyfx_agent_android';
        INSERT INTO public.app_versions(id,platform,latest_version,min_version,publish_date,created_at,updated_at,download_url,sha256)
        SELECT gen_random_uuid(),'storyfx_agent_android','{VERSION}','0.2.0',now(),now(),now(),'{URL}','{SHA}'
          WHERE NOT EXISTS(SELECT 1 FROM public.app_versions WHERE platform='storyfx_agent_android');
        NOTIFY pgrst,'reload schema'; COMMIT;"""
        phase = 'release_pointer_commit'
        sql(statement)
        committed = True
        phase = 'public_metadata_verification'
        metadata_url = 'https://api.formafx.com/functions/v1/storyfx-agent-download?platform=storyfx_agent_android&channel=stable&version=latest&asset_type=apk&metadata=1'
        verify_metadata(metadata_url)
    except Exception as error:
        print(json.dumps({'download_failure_phase': phase, 'error_kind': type(error).__name__,
                          'http_status': getattr(error, 'code', None),
                          'process_exit': getattr(error, 'returncode', None)}), flush=True)
        if committed:
            restore = "BEGIN; DELETE FROM public.app_versions WHERE platform='storyfx_agent_android';"
            if previous:
                encoded = json.dumps(previous).replace("'", "''")
                restore += "INSERT INTO public.app_versions SELECT (json_populate_record(NULL::public.app_versions,'" + encoded + "'::json)).*;"
            sql(restore + "NOTIFY pgrst,'reload schema'; COMMIT;")
        if existed:
            for source in (backup / 'storyfx-agent-download').iterdir():
                shutil.copy2(source, target / source.name)
        else:
            for source in target.iterdir():
                source.unlink()
            target.rmdir()
        if reload_needed:
            run('docker', 'restart', EDGE)
        raise RuntimeError('DOWNLOAD_FUNCTION_AND_POINTER_ROLLED_BACK') from None
    print(json.dumps({'download_install': 'success', 'url': URL, 'sha256': SHA,
                      'bytes': SIZE, 'backup': str(backup), 'edge_restart_required': reload_needed}))


if __name__ == '__main__':
    if len(sys.argv) == 3:
        configure(sys.argv[2])
    main(sys.argv[1])
