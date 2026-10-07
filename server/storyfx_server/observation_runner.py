"""Bounded private observation called by a dedicated timer, with no network/USB access."""
import json
import os
from pathlib import Path
import sys
import time
from .publication_observation import read_snapshot


def collect(folder, now=None):
    folder = Path(folder).resolve()
    config = json.loads((folder / 'observation-config.json').read_text())
    start, end = config['start_unix'], config['end_unix']
    if not 0 < end - start <= 7 * 86400:
        raise ValueError('OBSERVATION_WINDOW_INVALID')
    now = time.time() if now is None else now
    destination = folder / 'observation-state.json'
    state = json.loads(destination.read_text()) if destination.exists() else {
        'start_unix': start, 'end_unix': end, 'interval_minutes': 30, 'observations': []}
    if state['start_unix'] != start or state['end_unix'] != end:
        raise ValueError('OBSERVATION_WINDOW_MISMATCH')
    if now < start:
        return {'complete': False, 'waiting_for_start': True}
    if state.get('complete'):
        return summary(state)
    if state['observations'] and now < end + 900 and int(now) // 1800 == state['observations'][-1]['observed_unix'] // 1800:
        return summary(state)
    current = read_snapshot(folder / 'storyfx.db', config, now)
    state['observations'].append(current)
    state['complete'] = now >= end + 900
    state['read_only'] = True
    state['total_autonomy_verified'] = False
    temporary = destination.with_suffix('.pending')
    with temporary.open('w', encoding='utf-8') as output:
        os.chmod(temporary, 0o600)
        json.dump(state, output, indent=2)
    temporary.replace(destination)
    if state['complete']:
        marker = folder / 'observation-complete'
        marker.touch(mode=0o600)
    return summary(state)


def summary(state):
    last = state['observations'][-1]
    return {key: last[key] for key in ('observed_unix', 'totals', 'scheduler_enabled',
            'whatsapp_scope_violation', 'real_send_triggered_by_observer')} | {
                'complete': state['complete'], 'total_autonomy_verified': False,
                'connected_devices': sum(d['connected'] for d in last['devices'])}


if __name__ == '__main__':
    try:
        print(json.dumps(collect(sys.argv[1])))
    except Exception:
        print(json.dumps({'result': 'OBSERVATION_READ_FAILED', 'real_send_triggered_by_observer': False}))
        raise SystemExit(1)
