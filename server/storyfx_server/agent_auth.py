"""Browser consent, one-use tickets and S256 bind enrollment to its installation."""
import base64
import hashlib
import secrets
from urllib.parse import urlencode
from uuid import uuid4
from .store import DomainError, digest, timestamp


class AgentAuth:
    def __init__(self, store, sessions, origin):
        self.store, self.sessions, self.origin = store, sessions, origin
        with store.transaction() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS agent_auth_requests (
                id TEXT PRIMARY KEY, ciphertext TEXT NOT NULL, expires_at REAL NOT NULL,
                ticket_hash TEXT UNIQUE, ticket_expires_at REAL, session_id TEXT,
                subject TEXT, used_at REAL);''')

    def start(self, body):
        request_id = secrets.token_urlsafe(32)
        expires = self.store.clock() + 600
        with self.store.transaction() as db:
            db.execute('DELETE FROM agent_auth_requests WHERE expires_at<=?', (self.store.clock(),))
            db.execute('INSERT INTO agent_auth_requests(id,ciphertext,expires_at) VALUES (?,?,?)',
                       (digest(request_id), self.sessions.encrypt(body.model_dump(mode='json')), expires))
        return {'connect_url': self.origin + '/agent/connect?' + urlencode({'request_id': request_id}),
                'expires_at': timestamp(expires)}

    def authorize(self, request_id, principal):
        ticket = secrets.token_urlsafe(32)
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM agent_auth_requests WHERE id=?', (digest(request_id),)).fetchone()
            if not row or row['expires_at'] <= self.store.clock() or row['ticket_hash'] is not None:
                raise DomainError('AGENT_REQUEST_INVALID', 400)
            data = self.sessions.decrypt(row['ciphertext'])
            db.execute('UPDATE agent_auth_requests SET ticket_hash=?,ticket_expires_at=?,session_id=?,subject=? '
                       'WHERE id=?', (digest(ticket), self.store.clock() + 120,
                                     self.sessions.delegate(principal), principal['id'], row['id']))
        return {'redirect_to': data['redirect_uri'] + '?' + urlencode({'ticket': ticket, 'state': data['state']}),
                'device_name': data['name']}

    def describe(self, request_id):
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM agent_auth_requests WHERE id=?', (digest(request_id),)).fetchone()
        if not row or row['expires_at'] <= self.store.clock() or row['ticket_hash'] is not None:
            raise DomainError('AGENT_REQUEST_INVALID', 400)
        data = self.sessions.decrypt(row['ciphertext'])
        return {key: data[key] for key in ('name', 'android_version', 'app_version')}

    def exchange(self, body):
        # Read and authorize before the final atomic ticket consumption.
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM agent_auth_requests WHERE ticket_hash=?', (digest(body.ticket),)).fetchone()
        if not row or row['used_at'] is not None or row['ticket_expires_at'] <= self.store.clock():
            raise DomainError('AGENT_TICKET_INVALID', 401)
        data = self.sessions.decrypt(row['ciphertext'])
        challenge = base64.urlsafe_b64encode(hashlib.sha256(body.code_verifier.encode()).digest()).decode().rstrip('=')
        expected = {'state': body.state, 'device_nonce': body.device_nonce,
                    'installation_id': str(body.installation_id), 'code_challenge': challenge}
        if any(not secrets.compare_digest(data[key], value) for key, value in expected.items()):
            raise DomainError('AGENT_PROOF_INVALID', 401)
        principal = self.sessions.require_hash(row['session_id'])
        if principal['id'] != row['subject']:
            raise DomainError('UNAUTHORIZED', 401)
        credential = secrets.token_urlsafe(32)
        with self.store.transaction() as db:
            changed = db.execute('UPDATE agent_auth_requests SET used_at=? WHERE id=? AND used_at IS NULL '
                                 'AND ticket_expires_at>?', (self.store.clock(), row['id'], self.store.clock())).rowcount
            if not changed:
                raise DomainError('AGENT_TICKET_INVALID', 401)
            old = db.execute('SELECT id,owner_id FROM devices WHERE installation_id=?', (str(body.installation_id),)).fetchone()
            if old and old['owner_id'] != principal['id']:
                raise DomainError('INSTALLATION_ALREADY_ASSOCIATED', 409)
            device_id = old['id'] if old else str(uuid4())
            if old:
                db.execute("UPDATE jobs SET lease_hash=NULL,status=CASE WHEN status='QUEUED' THEN 'CANCELLED' "
                           "ELSE 'NEEDS_REVIEW' END WHERE device_id=? AND status IN ('QUEUED','CLAIMED','STARTED')", (device_id,))
                db.execute('UPDATE devices SET name=?,android_version=?,credential_hash=?,revoked=0,auth_session_hash=?,app_version=? '
                           'WHERE id=?', (data['name'], data['android_version'], digest(credential), row['session_id'], data['app_version'], device_id))
            else:
                db.execute('INSERT INTO devices(id,installation_id,name,android_version,credential_hash,created_at,owner_id,auth_session_hash,app_version) '
                           'VALUES (?,?,?,?,?,?,?,?,?)', (device_id, str(body.installation_id), data['name'], data['android_version'],
                                                          digest(credential), self.store.clock(), principal['id'], row['session_id'], data['app_version']))
        return {'device_id': device_id, 'token': credential, 'user': {key: principal[key] for key in ('id', 'email')}}
