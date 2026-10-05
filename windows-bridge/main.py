"""Explicit web launches only. No local scheduler, catch-up, or publication retry."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import msvcrt
from pathlib import Path
import secrets
import subprocess
import time
from api_client import Api
from secure_state import read, save

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.runtime' / 'windows-bridge'
STATE = PRIVATE / 'association.dpapi'
ADB = Path.home() / 'AppData/Local/Android/Sdk/platform-tools/adb.exe'


def available():
    from profile_settings import available as discover
    return discover(ROOT,ADB)


@contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def pair():
    if STATE.exists():
        print('Connecteur déjà associé. Aucun accès remplacé.'); return
    proof = secrets.token_urlsafe(32)
    response = Api().post('/v1/control/windows/start', {'name': 'Moteur StoryFX Windows', 'proof': proof})
    print('Dans StoryFX web, Lancement > Connecter Windows, autorisez cette demande :', flush=True)
    print(response['request_id'], flush=True)
    deadline = time.monotonic() + response['expires_in']
    while time.monotonic() < deadline:
        result = Api().post('/v1/control/windows/poll', {'request_id': response['request_id'], 'proof': proof})
        if not result.get('pending'):
            save(STATE, result)
            print('Connecteur associé. Accès chiffré avec Windows DPAPI.', flush=True); return
        time.sleep(3)
    raise RuntimeError('PAIRING_EXPIRED')


def run():
    import importlib.util
    if any(importlib.util.find_spec(name) is None for name in ('appium', 'selenium', 'PIL', 'requests')):
        raise RuntimeError('BRIDGE_REQUIREMENTS_MISSING')
    if not STATE.exists():
        pair()
    api = Api(read(STATE)['credential'])
    from publication_adapter import execute
    with exclusive(PRIVATE / 'connector.lock'):
        print('Moteur prêt. Seules les publications lancées dans le web seront exécutées.', flush=True)
        while True:
            try:
                from profile_settings import available as discover
                settings=api.post('/v1/control/windows/settings',{})
                profiles = discover(ROOT,ADB,settings['profiles'])
                api.post('/v1/control/windows/heartbeat', {'profiles': list(profiles)})
                flush(api)
                job = api.post('/v1/control/windows/claim', {}).get('job')
                if job:
                    handle(api, job, profiles, execute)
            except Exception:
                print('Liaison indisponible. Aucun lancement rejoué.', flush=True)
            time.sleep(10)


def handle(api, job, profiles, execute):
    identity = job['occurrence_id']
    if len(identity) != 64 or any(character not in '0123456789abcdef' for character in identity):
        raise RuntimeError('JOB_IDENTITY_INVALID')
    journal = PRIVATE / ('occurrence-' + identity + '.json')
    pending = PRIVATE / ('result-' + job['id'] + '.json')
    pending.write_text(json.dumps({'job_id': job['id'], 'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain'}))
    if journal.exists():
        result = json.loads(journal.read_text())
    else:
        result = {'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain'}
        journal.write_text(json.dumps(result))  # Crash-safe reservation before any phone action.
        try:
            payload = job['payload']
            profile = profiles.get(payload['device'])
            if not profile:
                result = {'state': 'FAILED_BEFORE_PUBLICATION', 'evidence': 'preflight_refused'}
            else:
                def authorize():
                    if api.post('/v1/control/windows/jobs/' + job['id'] + '/ready', {}).get('authorized') is not True:
                        raise RuntimeError('PUBLICATION_AUTHORIZATION_REFUSED')
                result = execute(ROOT, ADB, payload, profile, authorize)
        except Exception:
            pass  # A failed or ambiguous UI action never triggers a retry.
        result['completed_at'] = datetime.now(timezone.utc).isoformat()
        temporary = journal.with_suffix('.pending')
        temporary.write_text(json.dumps(result)); temporary.replace(journal)
    pending.write_text(json.dumps({'job_id': job['id'], **{key: result[key] for key in ('state', 'evidence')}}))
    flush(api)
    print('Résultat enregistré : ' + result['state'], flush=True)


def flush(api):
    # Retry only result acknowledgements. Never retry a phone action.
    for path in PRIVATE.glob('result-*.json'):
        value = json.loads(path.read_text())
        api.post('/v1/control/windows/jobs/' + value['job_id'] + '/complete', {key: value[key] for key in ('state', 'evidence')})
        path.rename(path.with_suffix('.acknowledged'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', action='store_true')
    args = parser.parse_args()
    try:
        pair() if args.pair else run()
    except KeyboardInterrupt:
        print('Connecteur arrêté. Aucun service Appium interrompu.')
    except Exception:
        raise SystemExit('Connexion indisponible. Vérifiez StoryFX web et la liaison Windows.')
