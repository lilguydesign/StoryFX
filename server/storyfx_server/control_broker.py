"""One-attempt Windows bridge; uncertain results never re-enter the queue."""
import json
import secrets
from uuid import uuid4
from .control_plan import plan, occurrence
from .store import DomainError, digest, timestamp
from .control_terminal import Terminal
from .control_publications import reserve
from .control_status_reviews import empty_review
from .control_media_modes import requires_media_v2
from .control_attempt_diagnostics import AttemptEvidence, schedule_status
from .control_native_channel_guard import guard_job


class Broker:
    def __init__(self, store, catalog, sessions):
        self.store, self.catalog, self.sessions = store, catalog, sessions
        self.terminal, self.scheduler = Terminal(store), None
        with store.transaction() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS control_nodes (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, auth_session TEXT NOT NULL,
                credential TEXT NOT NULL, name TEXT NOT NULL, last_seen REAL,
                profiles TEXT NOT NULL DEFAULT '[]', revoked INTEGER NOT NULL DEFAULT 0);
              CREATE TABLE IF NOT EXISTS control_pairs (
                id TEXT PRIMARY KEY, proof TEXT NOT NULL, expires REAL NOT NULL,
                name TEXT NOT NULL, owner_id TEXT, auth_session TEXT, consumed INTEGER DEFAULT 0);
              CREATE TABLE IF NOT EXISTS control_jobs (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, node_id TEXT,
                occurrence TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
                created REAL NOT NULL, claimed REAL, completed REAL, evidence TEXT,
                UNIQUE(owner_id,occurrence));
              CREATE TABLE IF NOT EXISTS control_seed_reports (owner_id TEXT PRIMARY KEY);
            ''')
            from .installation_hold import initialize
            initialize(db, control=True)
        from .control_android import AndroidControl
        self.android = AndroidControl(self)
        self.attempt_evidence = AttemptEvidence(store)
        from .control_recipes import Recipes
        self.recipes = Recipes(self)

    def begin(self, name, proof):
        self.store.throttle('control_pair', maximum=10, period=60)
        identity = str(uuid4())
        with self.store.transaction() as db:
            db.execute('DELETE FROM control_pairs WHERE expires<?', (self.store.clock(),))
            db.execute('INSERT INTO control_pairs(id,proof,expires,name) VALUES (?,?,?,?)',
                       (identity, digest(proof), self.store.clock() + 600, name))
        return {'request_id': identity, 'expires_in': 600}

    def approve(self, user, identity):
        if not self.sessions:
            raise DomainError('ACCOUNT_AUTH_REQUIRED', 503)
        with self.store.transaction() as db:
            changed = db.execute('UPDATE control_pairs SET owner_id=?,auth_session=? '
                                 'WHERE id=? AND expires>? AND owner_id IS NULL AND consumed=0',
                                 (user['id'], self.sessions.delegate(user), identity, self.store.clock())).rowcount
            if not changed:
                raise DomainError('PAIRING_INVALID', 409)
        return {'approved': True}

    def poll(self, identity, proof):
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM control_pairs WHERE id=? AND proof=? AND expires>?',
                             (identity, digest(proof), self.store.clock())).fetchone()
            if not row or row['consumed']:
                raise DomainError('PAIRING_INVALID', 409)
            if not row['owner_id']:
                return {'pending': True}
            token, node = secrets.token_urlsafe(32), str(uuid4())
            db.execute('INSERT INTO control_nodes(id,owner_id,auth_session,credential,name) VALUES (?,?,?,?,?)',
                       (node, row['owner_id'], row['auth_session'], digest(token), row['name']))
            db.execute('UPDATE control_pairs SET consumed=1 WHERE id=?', (identity,))
        return {'node_id': node, 'credential': token}

    def authenticate(self, token):
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM control_nodes WHERE credential=? AND revoked=0 '
                             'AND id NOT IN (SELECT node_id FROM control_android_links)', (digest(token),)).fetchone()
        if not row or not self.sessions:
            raise DomainError('UNAUTHORIZED', 401)
        user = self.sessions.require_hash(row['auth_session'])
        if user['id'] != row['owner_id']:
            raise DomainError('UNAUTHORIZED', 401)
        return dict(row)

    def snapshot(self, user):
        catalog = self.catalog.read(user)
        self.seed_report(user, catalog)
        with self.store.transaction() as db:
            db.execute("UPDATE control_jobs SET state='NEEDS_REVIEW' WHERE owner_id=? AND state IN ('CLAIMED','CANCEL_REQUESTED') AND claimed<?",
                       (user['id'], self.store.clock() - 900))
            nodes = [dict(row) for row in db.execute('SELECT id,name,last_seen,profiles,revoked FROM control_nodes WHERE owner_id=?', (user['id'],))]
            reports = [{**self.report(row), 'empty_status_review_available':empty_review(db, row, self.store.clock())}
                       for row in db.execute('SELECT * FROM control_jobs WHERE owner_id=? ORDER BY created DESC LIMIT 200', (user['id'],))]
            self.attempt_evidence.attach(db, reports, user['id'])
            attempts = list(db.execute('SELECT occurrence,state,payload FROM control_jobs WHERE owner_id=? ORDER BY created,id', (user['id'],)))
            states = {}
            depths = {}
            for attempt in attempts:
                payload = json.loads(attempt['payload'])
                root = payload.get('original_occurrence', attempt['occurrence'])
                depth = payload.get('retry_depth', 0)
                if depth >= depths.get(root, -1):
                    states[root], depths[root] = attempt['state'], depth
        for node in nodes:
            node['connected'] = not node['revoked'] and node['last_seen'] is not None and self.store.clock() - node['last_seen'] < 45
            node['profiles'] = json.loads(node['profiles'])
            node['last_seen'] = timestamp(node['last_seen'])
        self.android.enrich(nodes)
        schedules = plan(catalog, self.store.clock())
        for value in schedules:
            value['state'] = states.get(value['id'], 'PLANNED')
            value.update(schedule_status(value, {'nodes': nodes}))
            source = next(row for row in catalog['collections']['matrix'] if row['id'] == value['row_id'])
            value['page_reference'] = source.get('page') or None
        return {**catalog, 'nodes': nodes, 'schedule': schedules, 'reports': reports,
                'execution_mode': 'windows_and_android', 'autonomous_android_publication': False,
                'android_publication_capability': True, 'total_autonomy_verified': False,
                'scheduler':self.scheduler.status(user) if self.scheduler else {'enabled':False},
                'terminal':self.terminal.read(user)}

    @staticmethod
    def report(row):
        return {'id': row['id'], 'occurrence_id': row['occurrence'], 'state': row['state'],
                'created_at': timestamp(row['created']), 'completed_at': timestamp(row['completed']),
                'evidence': row['evidence'], 'publication': json.loads(row['payload'])}

    def seed_report(self, user, catalog):
        path = self.store.path.parent / 'control-seed.json'
        if not path.is_file():
            return
        seed = json.loads(path.read_text(encoding='utf-8-sig'))
        if seed.get('owner_email', '').casefold() != user.get('email', '').casefold():
            return
        with self.store.transaction() as db:
            if db.execute('SELECT 1 FROM control_seed_reports WHERE owner_id=?', (user['id'],)).fetchone():
                return
            for value in seed.get('confirmed_publications', []):
                rows = [row for row in catalog['collections']['matrix'] if row['device'] == value['profile']
                        and row['system'] == value['system'] and row['platform'] == 'WhatsApp' and row['engine'] == 'multi']
                if len(rows) != 1 or value['confirmed_media_count'] != rows[0]['count']:
                    raise DomainError('PRIVATE_RECEIPT_INVALID', 503)
                identity = occurrence(rows[0], value['scheduled_at'])
                payload = {**rows[0], 'due_at': value['scheduled_at'], 'execution_origin': 'local_python_appium', 'web_triggered': False}
                from datetime import datetime
                completed = datetime.fromisoformat(value['confirmed_at'].replace('Z', '+00:00')).timestamp() if value.get('confirmed_at') else self.store.clock()
                db.execute('INSERT OR IGNORE INTO control_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (str(uuid4()), user['id'], None, identity, json.dumps(payload), 'CONFIRMED',
                            completed, None, completed, value['provider_evidence']))
            db.execute('INSERT INTO control_seed_reports VALUES (?)', (user['id'],))

    def launch(self, user, body):
        snapshot = self.snapshot(user)
        if snapshot['revision'] != body.revision:
            raise DomainError('CONFIGURATION_CHANGED', 409)
        matches = [value for value in snapshot['schedule'] if value['id'] == body.occurrence_id]
        if len(matches) != 1:
            raise DomainError('OCCURRENCE_NOT_FOUND', 404)
        return reserve(self,user,snapshot,matches)[0]

    def heartbeat(self, node, profiles):
        with self.store.transaction() as db:
            db.execute('UPDATE control_nodes SET last_seen=?,profiles=? WHERE id=? AND revoked=0',
                       (self.store.clock(), json.dumps(profiles), node['id']))
        return {'received': True}

    def claim(self, node):
        with self.store.transaction() as db:
            if db.execute("SELECT 1 FROM control_jobs WHERE node_id=? AND state IN ('CLAIMED','CANCEL_REQUESTED')", (node['id'],)).fetchone():
                return {'job': None}
            row = db.execute("SELECT * FROM control_jobs WHERE node_id=? AND owner_id=? AND state='QUEUED' ORDER BY created LIMIT 1",
                             (node['id'], node['owner_id'])).fetchone()
            if not row:
                return {'job': None}
            guard_job(db, node, row, self.store.clock())
            from .control_phone_lock import phone_busy
            if phone_busy(db, node['owner_id'], json.loads(row['payload'])['device']):
                return {'job': None}
            due = json.loads(row['payload'])['due_at']
            from datetime import datetime
            if datetime.fromisoformat(due.replace('Z', '+00:00')).timestamp() > self.store.clock():
                return {'job': None}
            db.execute("UPDATE control_jobs SET state='CLAIMED',claimed=? WHERE id=? AND state='QUEUED'", (self.store.clock(), row['id']))
            payload = json.loads(row['payload'])
            self.terminal.emit(db,node['owner_id'],'CLAIMED',payload['device'],payload['system'])
        return {'job': {'id': row['id'], 'occurrence_id': row['occurrence'], 'payload': json.loads(row['payload'])}}

    def complete(self, node, identity, state, evidence, diagnostics=None):
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM control_jobs WHERE id=? AND node_id=? AND owner_id=?',
                             (identity, node['id'], node['owner_id'])).fetchone()
            if not row or row['state'] not in {'CLAIMED', 'CANCEL_REQUESTED', 'NEEDS_REVIEW', state}:
                raise DomainError('JOB_STATE_INVALID', 409)
            guard_job(db, node, row, self.store.clock(), receipt=True)
            if row['completed'] is not None and (row['state'] != state or row['evidence'] != evidence):
                raise DomainError('PUBLICATION_RESULT_ALREADY_RECORDED', 409)
            self.attempt_evidence.save(db, row, state, evidence, diagnostics)
            if row['completed'] is None and row['state'] in {'CLAIMED', 'CANCEL_REQUESTED', 'NEEDS_REVIEW'}:
                db.execute('UPDATE control_jobs SET state=?,completed=?,evidence=? WHERE id=?',
                           (state, self.store.clock(), evidence, identity))
                payload = json.loads(row['payload'])
                self.terminal.emit(db,node['owner_id'],state,payload['device'],payload['system'])
        return {'recorded': True}

    def ready(self, node, identity):
        with self.store.transaction() as db:
            row = db.execute("SELECT claimed,payload FROM control_jobs WHERE id=? AND node_id=? AND owner_id=? AND state='CLAIMED'",
                             (identity, node['id'], node['owner_id'])).fetchone()
            if not row or self.store.clock() - row['claimed'] > 900:
                raise DomainError('JOB_AUTHORIZATION_EXPIRED', 409)
            guard_job(db, node, row, self.store.clock())
            if 'media_modes_ready' in node and requires_media_v2(json.loads(row['payload'])) and not node['media_modes_ready']:
                raise DomainError('ANDROID_MEDIA_PERMISSION_REQUIRED', 409)
            self.catalog.revision(db,node['owner_id'],json.loads(row['payload'])['catalog_revision'])
        return {'authorized': True}
