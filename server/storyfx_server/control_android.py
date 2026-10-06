"""Owner-bound Android executors; no hardware grants or Windows credentials."""
import json
import secrets
from .control_status_reviews import record
from uuid import uuid4
from .store import DomainError, digest


class AndroidControl:
    def __init__(self, broker):
        self.broker, self.store = broker, broker.store
        with self.store.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS control_android_links (
              device_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, node_id TEXT UNIQUE NOT NULL,
              profile TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0,
              ready INTEGER NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT 'DISABLED',
              UNIQUE(owner_id,profile))''')
            db.execute('''CREATE TABLE IF NOT EXISTS control_status_reviews (
              node_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, profile TEXT NOT NULL, observed REAL NOT NULL)''')

    def principal(self, identity):
        if not self.broker.sessions or not identity.auth_session_hash:
            raise DomainError('ACCOUNT_AUTH_REQUIRED', 403)
        user = self.broker.sessions.require_hash(identity.auth_session_hash)
        if user['id'] != identity.owner_id:
            raise DomainError('UNAUTHORIZED', 401)
        return user

    def settings(self, identity):
        user = self.principal(identity)
        catalog = self.broker.catalog.read(user)
        profiles = [{'name': row['name'], 'enabled': row.get('enabled', True)}
                    for row in catalog['collections']['profiles']]
        with self.store.transaction() as db:
            self.store.authenticate_in_transaction(db, identity)
            link = db.execute('SELECT profile,enabled,reason FROM control_android_links WHERE device_id=? AND owner_id=?',
                              (identity.id, identity.owner_id)).fetchone()
        return {'profiles': profiles, 'binding': dict(link) if link else None,
                'executor': 'android_whatsapp_images_v1'}

    def bind(self, identity, body):
        user = self.principal(identity)
        profiles = self.broker.catalog.read(user)['collections']['profiles']
        if not any(p['name'] == body.profile and p.get('enabled', True) for p in profiles):
            raise DomainError('PROFILE_NOT_FOUND', 422)
        with self.store.transaction() as db:
            self.store.authenticate_in_transaction(db, identity)
            old = db.execute('SELECT * FROM control_android_links WHERE device_id=?', (identity.id,)).fetchone()
            occupied = db.execute('SELECT device_id FROM control_android_links WHERE owner_id=? AND profile=?',
                                  (identity.owner_id, body.profile)).fetchone()
            if occupied and occupied['device_id'] != identity.id:
                raise DomainError('ANDROID_PROFILE_ALREADY_BOUND', 409)
            if old and old['profile'] != body.profile and db.execute(
                    "SELECT 1 FROM control_jobs WHERE node_id=? AND state IN ('CLAIMED','CANCEL_REQUESTED')", (old['node_id'],)).fetchone():
                raise DomainError('PUBLICATION_IN_PROGRESS', 409)
            node = old['node_id'] if old else str(uuid4())
            if not old:
                db.execute('INSERT INTO control_nodes(id,owner_id,auth_session,credential,name) VALUES (?,?,?,?,?)',
                           (node, identity.owner_id, identity.auth_session_hash,
                            digest(secrets.token_urlsafe(32)), 'Agent Android StoryFX'))
            db.execute('INSERT INTO control_android_links VALUES (?,?,?,?,?,0,?) ON CONFLICT(device_id) '
                       'DO UPDATE SET profile=excluded.profile,enabled=excluded.enabled,ready=0,reason=excluded.reason',
                       (identity.id, identity.owner_id, node, body.profile, int(body.enabled), 'WAITING_PERMISSIONS' if body.enabled else 'DISABLED'))
            db.execute('UPDATE control_nodes SET last_seen=NULL,profiles=?,auth_session=? WHERE id=?',
                       (json.dumps([body.profile]), identity.auth_session_hash, node))
            if old:
                db.execute("UPDATE control_jobs SET state='CANCELLED',completed=? WHERE node_id=? AND state='QUEUED'", (self.store.clock(), node))
                db.execute("UPDATE control_jobs SET state='CANCEL_REQUESTED' WHERE node_id=? AND state='CLAIMED'", (node,))
        return self.settings(identity)

    def node(self, identity, *, require_ready=True):
        self.principal(identity)
        with self.store.transaction() as db:
            self.store.authenticate_in_transaction(db, identity)
            row = db.execute('SELECT n.*,a.enabled,a.ready,a.reason FROM control_nodes n JOIN control_android_links a '
                             'ON a.node_id=n.id WHERE a.device_id=? AND a.owner_id=? AND n.revoked=0',
                             (identity.id, identity.owner_id)).fetchone()
        if not row or require_ready and (not row['enabled'] or not row['ready'] or row['last_seen'] is None
                                         or self.store.clock() - row['last_seen'] >= 45):
            raise DomainError('ANDROID_EXECUTOR_NOT_READY', 409)
        return dict(row)

    def heartbeat(self, identity, body):
        node = self.node(identity, require_ready=False)
        reason = ('DISABLED' if not node['enabled'] else 'ACCESSIBILITY_REQUIRED' if not body.service_ready
                  else 'MEDIA_PERMISSION_REQUIRED' if not body.media_ready else 'SCREEN_LOCKED' if body.screen_locked else '')
        with self.store.transaction() as db:
            self.store.authenticate_in_transaction(db, identity)
            db.execute('UPDATE control_android_links SET ready=?,reason=? WHERE device_id=?', (int(not reason), reason, identity.id))
            record(db, node, body.own_status_empty, not reason, self.store.clock())
            db.execute('UPDATE control_nodes SET last_seen=?,auth_session=? WHERE id=?',
                       (self.store.clock() if not reason else None, identity.auth_session_hash, node['id']))
            db.execute('UPDATE devices SET last_seen=?,screen_locked=?,battery_percent=?,app_version=?,executor=? WHERE id=?',
                       (self.store.clock(), int(body.screen_locked), body.battery_percent, body.app_version,
                        'android_whatsapp_images_v1' if not reason else 'diagnostic', identity.id))
        return {'ready': not reason, 'reason': reason}

    def enrich(self, nodes):
        with self.store.transaction() as db:
            links = {row['node_id']: row for row in db.execute('SELECT a.*,d.revoked AS device_revoked FROM control_android_links a '
                     'JOIN devices d ON d.id=a.device_id')}
        for node in nodes:
            link = links.get(node['id'])
            node['executor'] = 'android_whatsapp_images_v1' if link else 'windows_bridge'
            if link:
                node['connected'] = bool(node['connected'] and link['ready'] and link['enabled'] and not link['device_revoked'])
                node['wait_reason'] = link['reason']
        return nodes


def executors(snapshot, value):
    nodes = [n for n in snapshot['nodes'] if n['connected'] and value['device'] in n['profiles']]
    windows = [n for n in nodes if n.get('executor', 'windows_bridge') == 'windows_bridge']
    images = (value['platform'] == 'WhatsApp' and value['engine'] == 'multi'
              and 1 <= value['count'] <= 30 and not value.get('page') and not value.get('page_name')
              and 'video' not in ''.join(value.get(key) or '' for key in ('system', 'album', 'album2')).casefold())
    native = [n for n in nodes if n.get('executor') == 'android_whatsapp_images_v1'] if images else []
    return native if native else windows
