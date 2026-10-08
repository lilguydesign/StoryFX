"""Read-only, owner-scoped evidence. Never instantiates the queue or an executor."""
from collections import Counter
from datetime import datetime, timedelta
import json
import sqlite3
from zoneinfo import ZoneInfo
from .control_plan import plan
from .control_publications import supported
from .control_media_modes import media_count, requires_media_v2
from .control_attempt_diagnostics import quantified_batch


def read_snapshot(database, config, now):
    owner = config['owner_id']
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        catalog = {'collections': {'profiles': [], 'systems': [], 'matrix': []}}
        for row in db.execute('SELECT id,collection,value FROM control_items WHERE owner_id=?', (owner,)):
            if row['collection'] in catalog['collections']:
                catalog['collections'][row['collection']].append({'id': row['id'], **json.loads(row['value'])})
        scheduler = db.execute('SELECT enabled,scope,wait_reason FROM control_schedulers WHERE owner_id=?', (owner,)).fetchone()
        scope = json.loads(scheduler['scope']) if scheduler else {'profiles': [], 'platforms': []}
        jobs = {}
        for row in db.execute('SELECT id,occurrence,state,payload,evidence FROM control_jobs WHERE owner_id=? ORDER BY created,id', (owner,)):
            payload = json.loads(row['payload'])
            occurrence = payload.get('original_occurrence', row['occurrence'])
            if payload.get('retry_depth', 0) >= jobs.get(occurrence, {}).get('depth', -1):
                jobs[occurrence] = {'state': row['state'], 'evidence': row['evidence'],
                                    'depth': payload.get('retry_depth', 0), 'id': row['id']}
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        diagnostics = {row['job_id']: json.loads(row['value']) for row in db.execute(
            'SELECT job_id,value FROM control_attempt_diagnostics WHERE owner_id=?', (owner,))
            } if 'control_attempt_diagnostics' in tables else {}
        media_capabilities = dict(db.execute('SELECT device_id,ready FROM control_android_media')) if 'control_android_media' in tables else {}
        rollout = db.execute("SELECT enabled_from FROM control_media_rollout WHERE name='media_v2'").fetchone() if 'control_media_rollout' in tables else None
        devices, capable_profiles = [], set()
        for row in db.execute('SELECT a.device_id,a.profile,a.enabled,a.ready,a.reason,d.last_seen,d.revoked,d.app_version '
                              'FROM control_android_links a JOIN devices d ON d.id=a.device_id WHERE a.owner_id=?', (owner,)):
            if row['profile'] in config['device_profiles']:
                if media_capabilities.get(row['device_id'], False):
                    capable_profiles.add(row['profile'])
                devices.append({'profile': row['profile'], 'connected': not row['revoked'] and
                                row['last_seen'] is not None and now - row['last_seen'] < 1200,
                                'publication_enabled': bool(row['enabled']), 'ready': bool(row['ready']),
                                'reason': row['reason'], 'version': row['app_version']})
    zone = ZoneInfo('Africa/Douala')
    day = datetime.fromtimestamp(config['start_unix'], zone).replace(hour=12, minute=0, second=0, microsecond=0)
    final = min(now, config['end_unix'])
    rows = []
    while day.date() <= datetime.fromtimestamp(final, zone).date():
        for value in plan(catalog, day.timestamp()):
            due = datetime.fromisoformat(value['due_at']).timestamp()
            if value['device'] not in config['schedule_profiles'] or not config['start_unix'] <= due <= final:
                continue
            job = jobs.get(value['id'], {'state': 'PLANNED', 'evidence': '', 'depth': 0})
            proof = diagnostics.get(job.get('id'))
            state = job['state']
            verdict = ('confirmed_agent' if state == 'CONFIRMED' and job['evidence'] == 'own_status_verified' else
                       'confirmed_legacy_unverified_count' if state == 'CONFIRMED' else
                       'uncertain' if state == 'NEEDS_REVIEW' else
                       'failed_before_send' if state == 'FAILED_BEFORE_PUBLICATION' else
                       'adapter_not_validated' if not supported(value) or requires_media_v2(value) and value['device'] not in capable_profiles else
                       'outside_media_rollout' if rollout and requires_media_v2(value) and due < rollout[0] else
                       'outside_active_scheduler' if value['device'] not in scope['profiles'] or value['platform'] not in scope['platforms'] else
                       'late' if now > due + 900 else 'waiting')
            rows.append({'occurrence': value['id'], 'profile': value['device'], 'platform': value['platform'],
                         'expected_count': value['count'], 'due_at': value['due_at'], 'state': state,
                         'engine': value['engine'], 'expected_media_count': media_count(value),
                         'verdict': verdict, 'retry_depth': job['depth'],
                         'batch_count_verified': verdict == 'confirmed_agent' and value['platform'] == 'WhatsApp'
                         and quantified_batch(proof, media_count(value)),
                         'diagnostics_available': proof is not None,
                         'account_verified': bool(proof and proof.get('account_verified')),
                         'facebook_page_and_batch_verified': False})
        day += timedelta(days=1)
    matrix = catalog['collections']['matrix']
    forbidden = sum(bool(r.get('enabled', True)) and r.get('platform') == 'WhatsApp' and
                    r.get('device') in config['whatsapp_forbidden_profiles'] for r in matrix)
    return {'observed_unix': int(now), 'scheduler_enabled': bool(scheduler and scheduler['enabled']),
            'scheduler_wait_reason': scheduler['wait_reason'] if scheduler else 'NOT_STARTED',
            'devices': devices, 'rows': rows, 'totals': dict(Counter(r['verdict'] for r in rows)),
            'whatsapp_scope_violation': bool(forbidden), 'read_only': True,
            'total_autonomy_verified': False, 'real_send_triggered_by_observer': False}
