"""Durable, operator-owned APK replacement exclusion; no scheduler or job mutation."""
import re
from .store import DomainError, digest

ERROR = 'ANDROID_INSTALLATION_HOLD'


def initialize(db, control=False):
    db.execute('''CREATE TABLE IF NOT EXISTS android_installation_holds (
        operation_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL, targets_hash TEXT NOT NULL, created REAL NOT NULL,
        released REAL, verification_sha256 TEXT)''')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS android_installation_owner_active '
               'ON android_installation_holds(owner_id) WHERE released IS NULL')
    table, state, owner = ('control_jobs', 'state', 'NEW.owner_id') if control else (
        'jobs', 'status', '(SELECT owner_id FROM devices WHERE id=NEW.device_id)')
    predicate = f'EXISTS(SELECT 1 FROM android_installation_holds WHERE owner_id={owner} AND released IS NULL)'
    for action, suffix, condition in (
        ('INSERT', 'insert', ''),
        ('UPDATE', 'dispatch', f" AND NEW.{state} IN ('QUEUED','CLAIMED','STARTED','CANCEL_REQUESTED')"),
    ):
        db.execute(f'''CREATE TRIGGER IF NOT EXISTS android_installation_{table}_{suffix}
            BEFORE {action} ON {table} WHEN {predicate}{condition}
            BEGIN SELECT RAISE(ABORT,'{ERROR}'); END''')


def operation_hash(key):
    if not isinstance(key, str) or re.fullmatch(r'[a-f0-9]{64}', key) is None:
        raise DomainError('INSTALLATION_OPERATION_INVALID', 400)
    return digest(key)


def require_idle(db, owner):
    if db.execute("SELECT 1 FROM control_jobs WHERE owner_id=? AND "
                  "(state IN ('QUEUED','CLAIMED','CANCEL_REQUESTED') OR "
                  "(state='NEEDS_REVIEW' AND completed IS NULL)) LIMIT 1", (owner,)).fetchone():
        raise DomainError('PUBLICATION_IN_PROGRESS')
    if db.execute("SELECT 1 FROM jobs JOIN devices ON jobs.device_id=devices.id WHERE devices.owner_id=? "
                  "AND jobs.status IN ('QUEUED','CLAIMED','STARTED','NEEDS_REVIEW') LIMIT 1", (owner,)).fetchone():
        raise DomainError('DEVICE_ACTIVITY_IN_PROGRESS')
    if db.execute('SELECT 1 FROM control_recipe_locks WHERE owner_id=?', (owner,)).fetchone() or db.execute(
            "SELECT 1 FROM control_recipes WHERE owner_id=? AND state!='RELEASED' LIMIT 1", (owner,)).fetchone():
        raise DomainError('MANUAL_RECIPE_ACTIVE')
    if db.execute('SELECT 1 FROM control_schedulers WHERE owner_id=? AND enabled=1', (owner,)).fetchone():
        raise DomainError('WINDOWS_USB_PAUSE_REQUIRED')


def acquire(store, owner, device_ids, key):
    operation = operation_hash(key)
    if not isinstance(device_ids, list) or not 1 <= len(device_ids) <= 2 or len(set(device_ids)) != len(device_ids):
        raise DomainError('INSTALLATION_TARGETS_INVALID', 400)
    targets = digest('|'.join(sorted(device_ids)))
    with store.transaction() as db:
        for device in device_ids:
            store.active_device(db, device, owner)
        prior = db.execute('SELECT * FROM android_installation_holds WHERE operation_hash=?', (operation,)).fetchone()
        if prior:
            if prior['owner_id'] != owner or prior['released'] is not None or prior['targets_hash'] != targets:
                raise DomainError('INSTALLATION_OPERATION_ALREADY_USED')
            require_idle(db, owner)
            return {'held': True, 'created': False, 'automatic_expiry': False}
        if db.execute('SELECT 1 FROM android_installation_holds WHERE owner_id=? AND released IS NULL', (owner,)).fetchone():
            raise DomainError('INSTALLATION_ALREADY_HELD')
        require_idle(db, owner)
        db.execute('INSERT INTO android_installation_holds(operation_hash,owner_id,targets_hash,created) VALUES (?,?,?,?)',
                   (operation, owner, targets, store.clock()))
    return {'held': True, 'created': True, 'automatic_expiry': False}


def status(store, owner, key):
    operation = operation_hash(key)
    with store.transaction() as db:
        row = db.execute('SELECT released FROM android_installation_holds WHERE owner_id=? AND operation_hash=?',
                         (owner, operation)).fetchone()
    if row is None:
        raise DomainError('INSTALLATION_HOLD_NOT_FOUND', 404)
    return {'held': row['released'] is None, 'automatic_expiry': False}


def release(store, owner, key, verification_sha256):
    operation = operation_hash(key)
    if not isinstance(verification_sha256, str) or re.fullmatch('[a-f0-9]{64}', verification_sha256) is None:
        raise DomainError('INSTALLATION_VERIFICATION_REQUIRED', 400)
    with store.transaction() as db:
        row = db.execute('SELECT * FROM android_installation_holds WHERE owner_id=? AND operation_hash=?',
                         (owner, operation)).fetchone()
        if row is None:
            raise DomainError('INSTALLATION_HOLD_NOT_FOUND', 404)
        if row['released'] is not None:
            if row['verification_sha256'] != verification_sha256:
                raise DomainError('INSTALLATION_RELEASE_ALREADY_RECORDED')
        else:
            require_idle(db, owner)
            db.execute('UPDATE android_installation_holds SET released=?,verification_sha256=? WHERE operation_hash=?',
                       (store.clock(), verification_sha256, operation))
    return {'held': False, 'released': True, 'automatic_expiry': False}
