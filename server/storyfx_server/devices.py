"""One-use enrollment and revocation; credentials are stored only as hashes."""
import secrets
from uuid import uuid4
from .store import DomainError, digest, timestamp


def create_pairing(store):
    code = secrets.token_hex(8).upper()
    expires = store.clock() + 600
    with store.transaction() as db:
        db.execute('INSERT INTO pairings(code_hash,expires_at) VALUES (?,?)', (digest(code), expires))
    return {'code': code, 'expires_at': timestamp(expires)}


def enroll(store, request):
    credential = secrets.token_urlsafe(32)
    with store.transaction() as db:
        code = db.execute('SELECT * FROM pairings WHERE code_hash=?',
                          (digest(request.code.strip().upper()),)).fetchone()
        if not code or code['used_at'] is not None or code['expires_at'] <= store.clock():
            raise DomainError('PAIRING_INVALID_OR_EXPIRED', 400)
        old = db.execute('SELECT id FROM devices WHERE installation_id=?',
                         (str(request.installation_id),)).fetchone()
        device_id = old['id'] if old else str(uuid4())
        if old:
            db.execute("UPDATE jobs SET status='NEEDS_REVIEW' WHERE device_id=? "
                       "AND status IN ('CLAIMED','STARTED')", (device_id,))
            # Invalidate the former installation attempt, including its outbox.
            db.execute('UPDATE jobs SET lease_hash=NULL WHERE device_id=?', (device_id,))
            db.execute('UPDATE devices SET name=?,android_version=?,credential_hash=?,revoked=0 '
                       'WHERE id=?', (request.name, request.android_version, digest(credential), device_id))
        else:
            db.execute('INSERT INTO devices(id,installation_id,name,android_version,credential_hash,created_at) '
                       'VALUES (?,?,?,?,?,?)', (device_id, str(request.installation_id), request.name,
                                              request.android_version, digest(credential), store.clock()))
        db.execute('UPDATE pairings SET used_at=? WHERE code_hash=?',
                   (store.clock(), digest(request.code.strip().upper())))
    return {'device_id': device_id, 'token': credential}


def heartbeat(store, identity, request):
    with store.transaction() as db:
        device_id = store.authenticate_in_transaction(db, identity)
        db.execute('UPDATE devices SET last_seen=?,battery_percent=?,screen_locked=?,executor=?,app_version=? '
                   'WHERE id=?', (store.clock(), request.battery_percent, int(request.screen_locked),
                                 request.executor, request.app_version, device_id))
    return {}


def revoke(store, device_id):
    with store.transaction() as db:
        changed = db.execute('UPDATE devices SET revoked=1 WHERE id=?', (device_id,)).rowcount
        if not changed:
            raise DomainError('DEVICE_NOT_FOUND', 404)
        db.execute("UPDATE jobs SET status=CASE WHEN status='QUEUED' THEN 'CANCELLED' ELSE 'NEEDS_REVIEW' END, "
                   "lease_hash=NULL WHERE device_id=? AND status IN ('QUEUED','CLAIMED','STARTED')", (device_id,))
    return {}
