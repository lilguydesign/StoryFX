"""Explicit Facebook profile permissions, inert until a native adapter is validated."""
import json
from uuid import uuid4
from .store import DomainError, fingerprint, timestamp
from .control_facebook_foundation import capability


def capabilities():
    return {'facebook': capability()}


def require_idle(db, owner, device):
    # Include expired claims without receipts: a timeout does not prove gestures stopped.
    if db.execute("SELECT 1 FROM control_jobs WHERE owner_id=? AND completed IS NULL "
                  "AND state IN ('QUEUED','CLAIMED','CANCEL_REQUESTED','NEEDS_REVIEW') LIMIT 1", (owner,)).fetchone():
        raise DomainError('PUBLICATION_IN_PROGRESS', 409)
    if db.execute("SELECT 1 FROM jobs WHERE device_id=? AND status IN ('QUEUED','CLAIMED','STARTED') LIMIT 1", (device,)).fetchone():
        raise DomainError('DEVICE_ACTIVITY_IN_PROGRESS', 409)
    if db.execute('SELECT 1 FROM control_recipe_locks WHERE owner_id=?', (owner,)).fetchone():
        raise DomainError('MANUAL_RECIPE_ACTIVE', 409)


def secondary_profile_bound(db, owner, profile):
    return db.execute('''SELECT 1 FROM control_android_profiles a JOIN control_items p ON p.id=a.profile_id
      AND p.owner_id=a.owner_id AND p.collection='profiles'
      WHERE a.owner_id=? AND p.json_name=? AND a.revoked IS NULL''', (owner, profile)).fetchone() is not None


class AndroidProfileBindings:
    def __init__(self, native):
        self.native, self.store = native, native.store
        with self.store.transaction() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS control_android_profiles (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, device_id TEXT NOT NULL,
                node_id TEXT NOT NULL, profile_id TEXT NOT NULL,
                platform TEXT NOT NULL CHECK(platform='Facebook'),
                client_key TEXT NOT NULL, request_hash TEXT NOT NULL,
                created REAL NOT NULL, revoked REAL, UNIQUE(owner_id,client_key));
              CREATE UNIQUE INDEX IF NOT EXISTS control_android_profile_active
                ON control_android_profiles(owner_id,profile_id) WHERE revoked IS NULL;
            ''')

    @staticmethod
    def view(db, row):
        profile = db.execute("SELECT json_name,value FROM control_items WHERE id=? AND owner_id=? AND collection='profiles'",
                             (row['profile_id'], row['owner_id'])).fetchone()
        enabled = bool(profile and json.loads(profile['value']).get('enabled', True))
        reason = ('BINDING_REMOVED' if row['revoked'] is not None else 'PROFILE_NOT_FOUND' if not profile
                  else 'PROFILE_DISABLED' if not enabled else 'ADAPTER_NOT_VALIDATED')
        return {'id': row['id'], 'client_key': row['client_key'], 'device_id': row['device_id'],
                'profile_id': row['profile_id'], 'profile': profile['json_name'] if profile else None,
                'platform': row['platform'], 'active': row['revoked'] is None,
                'enabled': enabled, 'ready': False, 'reason': reason,
                'created_at': timestamp(row['created']), 'revoked_at': timestamp(row['revoked'])}

    def listing(self, user):
        self.native.broker.catalog.ensure(user)
        with self.store.transaction() as db:
            revision = db.execute('SELECT revision FROM control_owners WHERE owner_id=?', (user['id'],)).fetchone()[0]
            rows = db.execute('SELECT * FROM control_android_profiles WHERE owner_id=? ORDER BY created,id', (user['id'],)).fetchall()
            devices = [dict(row) for row in db.execute('''SELECT d.id AS device_id,d.name,
              p.id AS primary_profile_id,p.json_name AS primary_profile FROM control_android_links a
              JOIN control_nodes n ON n.id=a.node_id AND n.owner_id=a.owner_id AND n.revoked=0
              JOIN devices d ON d.id=a.device_id AND d.owner_id=a.owner_id AND d.revoked=0
              JOIN control_items p ON p.owner_id=a.owner_id AND p.collection='profiles' AND p.json_name=a.profile
              WHERE a.owner_id=? ORDER BY d.name,d.id''', (user['id'],))]
            primary_ids = [row['id'] for row in db.execute('''SELECT p.id FROM control_android_links a
              JOIN control_items p ON p.owner_id=a.owner_id AND p.collection='profiles' AND p.json_name=a.profile
              WHERE a.owner_id=? ORDER BY p.id''', (user['id'],))]
            return {'revision': revision, 'bindings': [self.view(db, row) for row in rows], 'capabilities': capabilities(),
                    'devices': [{**row, 'revoked': False} for row in devices], 'primary_profile_ids': primary_ids}

    def add(self, user, body):
        owner, device, profile = user['id'], str(body.device_id), str(body.profile_id)
        request_hash = fingerprint(body.model_dump(mode='json', exclude={'client_key'}))
        with self.store.transaction() as db:
            prior = db.execute('SELECT * FROM control_android_profiles WHERE owner_id=? AND client_key=?',
                               (owner, str(body.client_key))).fetchone()
            if prior:
                if prior['request_hash'] != request_hash:
                    raise DomainError('IDEMPOTENCY_KEY_CONFLICT', 409)
                return self.view(db, prior)
            self.native.broker.catalog.revision(db, owner, body.revision)
            self.store.active_device(db, device, owner)
            link = db.execute('''SELECT a.* FROM control_android_links a JOIN control_nodes n
              ON n.id=a.node_id AND n.owner_id=a.owner_id AND n.revoked=0
              WHERE a.device_id=? AND a.owner_id=?''', (device, owner)).fetchone()
            if not link:
                raise DomainError('ANDROID_PRIMARY_BINDING_REQUIRED', 409)
            target = db.execute("SELECT json_name,value FROM control_items WHERE owner_id=? AND collection='profiles' AND id=?",
                                (owner, profile)).fetchone()
            if not target or not json.loads(target['value']).get('enabled', True):
                raise DomainError('PROFILE_NOT_FOUND', 422)
            if db.execute('SELECT 1 FROM control_android_links WHERE owner_id=? AND profile=?', (owner, target['json_name'])).fetchone() or db.execute(
                    'SELECT 1 FROM control_android_profiles WHERE owner_id=? AND profile_id=? AND revoked IS NULL', (owner, profile)).fetchone():
                raise DomainError('ANDROID_PROFILE_ALREADY_BOUND', 409)
            require_idle(db, owner, device)
            if db.execute('SELECT COUNT(*) FROM control_android_profiles WHERE owner_id=? AND device_id=? AND revoked IS NULL',
                          (owner, device)).fetchone()[0] >= 99:
                raise DomainError('ANDROID_PROFILE_LIMIT_REACHED', 409)
            identity = str(uuid4())
            db.execute('INSERT INTO control_android_profiles VALUES (?,?,?,?,?,?,?,?,?,NULL)',
                       (identity, owner, device, link['node_id'], profile, 'Facebook', str(body.client_key), request_hash, self.store.clock()))
            return self.view(db, db.execute('SELECT * FROM control_android_profiles WHERE id=?', (identity,)).fetchone())

    def remove(self, user, identity, revision):
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM control_android_profiles WHERE id=? AND owner_id=?', (identity, user['id'])).fetchone()
            if not row:
                raise DomainError('ANDROID_PROFILE_BINDING_NOT_FOUND', 404)
            if row['revoked'] is None:
                self.native.broker.catalog.revision(db, user['id'], revision)
                require_idle(db, user['id'], row['device_id'])
                db.execute('UPDATE control_android_profiles SET revoked=? WHERE id=?', (self.store.clock(), identity))
            return self.view(db, db.execute('SELECT * FROM control_android_profiles WHERE id=?', (identity,)).fetchone())

    @staticmethod
    def authorized(db, identity, link, now):
        if not link:
            return []
        primary = db.execute("SELECT id,value FROM control_items WHERE owner_id=? AND collection='profiles' AND json_name=?",
                             (identity.owner_id, link['profile'])).fetchone()
        enabled = bool(primary and json.loads(primary['value']).get('enabled', True))
        ready = bool(link['ready'] and link['enabled'] and enabled and not link['revoked']
                     and link['last_seen'] is not None and 0 <= now - link['last_seen'] < 45)
        values = [{'profile_id': primary['id'] if primary else None, 'profile': link['profile'],
                   'platform': 'WhatsApp', 'primary': True, 'enabled': bool(link['enabled'] and enabled),
                   'ready': ready, 'reason': link['reason'] or ('' if ready else 'ANDROID_EXECUTOR_NOT_READY')}]
        for row in db.execute('''SELECT a.*,p.json_name,p.value FROM control_android_profiles a
          JOIN control_items p ON p.id=a.profile_id AND p.owner_id=a.owner_id AND p.collection='profiles'
          WHERE a.owner_id=? AND a.device_id=? AND a.node_id=? AND a.revoked IS NULL ORDER BY a.created,a.id''',
                              (identity.owner_id, identity.id, link['node_id'])):
            values.append({'profile_id': row['profile_id'], 'profile': row['json_name'], 'platform': 'Facebook',
                           'primary': False, 'enabled': bool(json.loads(row['value']).get('enabled', True)),
                           'ready': False, 'reason': 'ADAPTER_NOT_VALIDATED'})
        return values
