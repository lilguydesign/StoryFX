"""Diagnostic queue: atomic claims, installation exclusion and safe late acknowledgement."""
import secrets
from uuid import uuid4
from .store import DomainError, digest, fingerprint, timestamp


def enqueue(store, request, owner_id='validation_owner'):
    due, expires = request.scheduled_at.timestamp(), request.expires_at.timestamp()
    if expires <= due or expires <= store.clock() or expires - due > 86400:
        raise DomainError('INVALID_TIME_WINDOW', 400)
    key = f'diagnostic|{request.device_id}|{due:.6f}'
    with store.transaction() as db:
        store.active_device(db, str(request.device_id), owner_id)
        old = db.execute('SELECT * FROM jobs WHERE occurrence_key=?', (key,)).fetchone()
        if old:
            if old['expires_at'] != expires:
                raise DomainError('OCCURRENCE_CONFLICT')
            return {'job': store.job_view(old), 'duplicate': True}
        identity = str(uuid4())
        db.execute('INSERT INTO jobs(id,occurrence_key,device_id,kind,status,scheduled_at,expires_at,created_at) '
                   "VALUES (?,?,?,'diagnostic','QUEUED',?,?,?)",
                   (identity, key, str(request.device_id), due, expires, store.clock()))
        row = db.execute('SELECT * FROM jobs WHERE id=?', (identity,)).fetchone()
    return {'job': store.job_view(row), 'duplicate': False}


def claim(store, identity):
    with store.transaction() as db:
        device_id = store.authenticate_in_transaction(db, identity)
        store.recover(db)
        # Review holds the device until an authenticated late result resolves it.
        if db.execute("SELECT id FROM jobs WHERE device_id=? AND status IN "
                      "('CLAIMED','STARTED','NEEDS_REVIEW')", (device_id,)).fetchone():
            return {'job': None}
        row = db.execute("SELECT * FROM jobs WHERE device_id=? AND status='QUEUED' AND scheduled_at<=? "
                         'ORDER BY scheduled_at,id LIMIT 1', (device_id, store.clock())).fetchone()
        if row is None:
            return {'job': None}
        lease = secrets.token_urlsafe(32)
        lease_until = min(store.clock() + 120, row['expires_at'])
        db.execute("UPDATE jobs SET status='CLAIMED',attempt=attempt+1,lease_hash=?,lease_expires_at=? "
                   'WHERE id=?', (digest(lease), lease_until, row['id']))
        result = store.job_view(db.execute('SELECT * FROM jobs WHERE id=?', (row['id'],)).fetchone())
        result.update(lease_token=lease, lease_expires_at=timestamp(lease_until))
    return {'job': result}


def renew(store, identity, job_id, lease):
    with store.transaction() as db:
        device_id = store.authenticate_in_transaction(db, identity)
        store.recover(db)
        row = db.execute('SELECT * FROM jobs WHERE id=? AND device_id=?', (job_id, device_id)).fetchone()
        if not row or row['lease_hash'] != digest(lease) or row['status'] not in ('CLAIMED', 'STARTED'):
            raise DomainError('LEASE_INVALID')
        expires = min(store.clock() + 120, row['expires_at'])
        if expires <= store.clock():
            raise DomainError('LEASE_EXPIRED')
        db.execute('UPDATE jobs SET lease_expires_at=? WHERE id=?', (expires, job_id))
    return {'lease_expires_at': timestamp(expires)}


def cancel(store, job_id, owner_id='validation_owner'):
    with store.transaction() as db:
        row = db.execute('SELECT jobs.status FROM jobs JOIN devices ON jobs.device_id=devices.id '
                         'WHERE jobs.id=? AND devices.owner_id=?', (job_id, owner_id)).fetchone()
        if row is None:
            raise DomainError('JOB_NOT_FOUND', 404)
        if row['status'] == 'DIAGNOSTIC_CONFIRMED':
            raise DomainError('CONFIRMED_JOB_IMMUTABLE')
        db.execute("UPDATE jobs SET status='CANCELLED',lease_hash=NULL WHERE id=?", (job_id,))
    return {}


def receive_event(store, identity, job_id, request):
    with store.transaction() as db:
        device_id = store.authenticate_in_transaction(db, identity)
        payload_hash = fingerprint({'job_id': job_id, 'device_id': device_id,
                                    **request.model_dump(mode='json')})
        old = db.execute('SELECT * FROM events WHERE id=?', (str(request.event_id),)).fetchone()
        if old:
            if old['payload_hash'] != payload_hash:
                raise DomainError('EVENT_ID_CONFLICT')
            return {'accepted': True, 'duplicate': True}
        row = db.execute('SELECT * FROM jobs WHERE id=? AND device_id=?', (job_id, device_id)).fetchone()
        if not row or row['lease_hash'] != digest(request.lease_token):
            raise DomainError('LEASE_INVALID')
        prior_start = db.execute("SELECT id FROM events WHERE job_id=? AND stage='STARTED'", (job_id,)).fetchone()
        expected = ('CLAIMED', 'NEEDS_REVIEW') if request.stage == 'STARTED' else ('STARTED', 'NEEDS_REVIEW')
        if row['status'] not in expected or (request.stage == 'DIAGNOSTIC_CONFIRMED' and not prior_start):
            raise DomainError('INVALID_STAGE_TRANSITION')
        db.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',
                   (str(request.event_id), job_id, device_id, payload_hash, request.stage, store.clock()))
        # This is diagnostic transport confirmation, never a story publication.
        db.execute('UPDATE jobs SET status=?,last_event_at=? WHERE id=?',
                   (request.stage, store.clock(), job_id))
    return {'accepted': True, 'duplicate': False}
