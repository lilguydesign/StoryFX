"""Owner-scoped scheduler proof, independent of USB and publication dispatch."""
import json
import subprocess


def evaluate(evidence):
    if not isinstance(evidence, dict) or evidence.get('read_only') is not True:
        status, reason = 'unknown', 'STORYFX_SCHEDULER_PROOF_MISSING'
    elif not evidence['enabled']:
        status, reason = ('incident', 'STORYFX_SCHEDULER_PAUSED') if evidence['wait_reason'] else (
            'disabled', 'STORYFX_SCHEDULER_STOPPED')
    elif evidence['wait_reason'] in {'AUTH_UNAVAILABLE', 'RATE_LIMITED'}:
        bounded = evidence.get('next_check_in_seconds') is not None and -60 <= evidence['next_check_in_seconds'] <= 300
        status, reason = ('waiting', 'STORYFX_CONTROL_RECHECK_PENDING') if bounded else (
            'incident', 'STORYFX_CONTROL_RECHECK_STALE')
    else:
        status, reason = ('waiting', 'STORYFX_EXECUTOR_WAITING') if evidence['wait_reason'] else (
            'ok', 'STORYFX_SCHEDULER_ACTIVE')
    return {'id': 'storyfx_scheduler_recovery', 'status': status, 'reason_code': reason,
            'metrics': evidence or {}, 'read_only': True, 'notifications_sent': False,
            'real_send_triggered': False, 'total_autonomy_verified': False}


def collect():
    remote = """import json,sqlite3,time
from pathlib import Path
root=Path('/opt/formafx/storyfx/state')
owner=json.loads((root/'observation-config.json').read_text())['owner_id']
with sqlite3.connect((root/'storyfx.db').as_uri()+'?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 db.execute('PRAGMA query_only=ON')
 s=db.execute('SELECT enabled,generation,wait_reason FROM control_schedulers WHERE owner_id=?',(owner,)).fetchone()
 assert s is not None
 w=db.execute('SELECT next_check,failures,status FROM control_scheduler_waits WHERE owner_id=? AND generation=?',(owner,s['generation'])).fetchone()
 print(json.dumps({'enabled':bool(s['enabled']),'wait_reason':s['wait_reason'],
  'next_check_in_seconds':round(w['next_check']-time.time()) if w else None,
  'consecutive_failures':w['failures'] if w else 0,'last_control_http_status':w['status'] if w else None,
  'read_only':True,'usb_required':False}))
"""
    try:
        result = subprocess.run(['ssh', '-o', 'BatchMode=yes', 'formafx-db', 'sudo python3 -'],
                                input=remote, text=True, capture_output=True, timeout=45)
        return evaluate(json.loads(result.stdout) if result.returncode == 0 else None)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return evaluate(None)


if __name__ == '__main__':
    print(json.dumps(collect()))
