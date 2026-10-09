"""Durable transactions. No GUI, Appium, subprocesses or publication adapters."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def timestamp(value: float | None) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


def fingerprint(value: dict) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':')))


class DomainError(Exception):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code, self.status = code, status


@dataclass(frozen=True)
class DeviceIdentity:
    id: str
    credential_hash: str
    owner_id: str = 'validation_owner'
    auth_session_hash: str | None = None


class Store:
    def __init__(self, path: Path, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript(Path(__file__).with_name('schema.sql').read_text())
            from .schema_upgrade import upgrade
            upgrade(db)
            from .installation_hold import initialize
            initialize(db)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except sqlite3.IntegrityError as error:
            db.rollback()
            if str(error) == 'ANDROID_INSTALLATION_HOLD':
                raise DomainError('ANDROID_INSTALLATION_HOLD') from None
            raise
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def device(self, credential: str) -> DeviceIdentity:
        credential_hash = digest(credential)
        with self.transaction() as db:
            row = db.execute('SELECT id,owner_id,auth_session_hash FROM devices WHERE credential_hash=? AND revoked=0',
                             (credential_hash,)).fetchone()
        if row is None:
            raise DomainError('UNAUTHORIZED', 401)
        return DeviceIdentity(row['id'], credential_hash, row['owner_id'], row['auth_session_hash'])

    def authenticate_in_transaction(self, db, identity: DeviceIdentity) -> str:
        row = db.execute('SELECT id FROM devices WHERE id=? AND credential_hash=? AND revoked=0',
                         (identity.id, identity.credential_hash)).fetchone()
        if row is None:
            raise DomainError('UNAUTHORIZED', 401)
        return identity.id

    @staticmethod
    def active_device(db, device_id, owner_id='validation_owner'):
        if db.execute('SELECT id FROM devices WHERE id=? AND owner_id=? AND revoked=0', (device_id, owner_id)).fetchone() is None:
            raise DomainError('DEVICE_NOT_FOUND_OR_REVOKED', 404)

    def recover(self, db):
        now = self.clock()
        db.execute("UPDATE jobs SET status='NEEDS_REVIEW' WHERE status IN ('CLAIMED','STARTED') "
                   'AND lease_expires_at<=?', (now,))
        db.execute("UPDATE jobs SET status='EXPIRED' WHERE status='QUEUED' AND expires_at<=?", (now,))

    def throttle(self, bucket: str, maximum=20, period=60):
        with self.transaction() as db:
            now = self.clock()
            row = db.execute('SELECT * FROM throttles WHERE bucket=?', (bucket,)).fetchone()
            if row and now - row['window_start'] < period:
                if row['count'] >= maximum:
                    raise DomainError('RATE_LIMITED', 429)
                db.execute('UPDATE throttles SET count=count+1 WHERE bucket=?', (bucket,))
            else:
                db.execute('INSERT OR REPLACE INTO throttles VALUES (?,?,1)', (bucket, now))

    def dashboard(self, owner_id='validation_owner'):
        with self.transaction() as db:
            self.recover(db)
            devices = [dict(row) for row in db.execute(
                'SELECT id,name,last_seen,battery_percent,screen_locked,revoked,executor,app_version '
                'FROM devices WHERE owner_id=? ORDER BY created_at DESC LIMIT 200', (owner_id,))]
            for item in devices:
                item['last_seen'] = timestamp(item['last_seen'])
                item['screen_locked'], item['revoked'] = bool(item['screen_locked']), bool(item['revoked'])
            jobs = [self.job_view(row) for row in db.execute(
                'SELECT jobs.* FROM jobs JOIN devices ON jobs.device_id=devices.id WHERE devices.owner_id=? '
                'ORDER BY jobs.created_at DESC LIMIT 200', (owner_id,))]
            counts = dict(db.execute('SELECT jobs.status,COUNT(*) FROM jobs JOIN devices ON jobs.device_id=devices.id '
                                     'WHERE devices.owner_id=? GROUP BY jobs.status', (owner_id,)).fetchall())
        return {'devices': devices, 'jobs': jobs, 'mode': 'diagnostic_only',
                'server_time': timestamp(self.clock()), 'metrics': {
                    'devices': sum(not item['revoked'] for item in devices),
                    'total_jobs': sum(counts.values()), 'completed': counts.get('DIAGNOSTIC_CONFIRMED', 0),
                    'waiting': sum(counts.get(key, 0) for key in ('QUEUED', 'CLAIMED', 'STARTED')),
                    'needs_review': counts.get('NEEDS_REVIEW', 0)}}

    @staticmethod
    def job_view(row):
        keys = ('id', 'device_id', 'kind', 'status', 'attempt')
        result = {key: row[key] for key in keys}
        result.update({key: timestamp(row[key]) for key in
                       ('scheduled_at', 'expires_at', 'created_at', 'lease_expires_at')})
        return result
