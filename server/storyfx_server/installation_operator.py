"""Local privileged operator only; JSON stdin, closed stdout, no HTTP access or sends."""
import json
from pathlib import Path
import sqlite3
import sys
from .installation_hold import acquire, release, status
from .store import DomainError, Store


def main(database, stream, output):
    # Existing production schema only: do not create a database on a mistyped path.
    path = Path(database).resolve(strict=True)
    with sqlite3.connect('file:' + path.as_posix() + '?mode=ro', uri=True) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'android_installation_holds', 'control_jobs', 'control_recipe_locks', 'control_schedulers'} <= tables:
        raise DomainError('INSTALLATION_BACKEND_REQUIRED')
    raw = stream.read(8193)
    if len(raw) > 8192:
        raise DomainError('INSTALLATION_REQUEST_INVALID', 400)
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise DomainError('INSTALLATION_REQUEST_INVALID', 400)
    action = body.get('action')
    fields = {'action', 'owner_id', 'operation_key'}
    fields |= {'device_ids'} if action == 'acquire' else {'verification_sha256'} if action == 'release' else set()
    if set(body) != fields or action not in ('acquire', 'status', 'release'):
        raise DomainError('INSTALLATION_REQUEST_INVALID', 400)
    store = Store(path)
    arguments = (store, body['owner_id'])
    if action == 'acquire':
        result = acquire(*arguments, body['device_ids'], body['operation_key'])
    elif action == 'release':
        result = release(*arguments, body['operation_key'], body['verification_sha256'])
    else:
        result = status(*arguments, body['operation_key'])
    output.write(json.dumps(result) + '\n')


if __name__ == '__main__':
    try:
        main(sys.argv[1], sys.stdin, sys.stdout)
    except Exception as error:
        reason = error.code if isinstance(error, DomainError) else type(error).__name__ + ':DETAILS_WITHHELD'
        print(json.dumps({'result': 'blocked', 'reason': reason}))
        sys.exit(1)
