"""Opaque cookies and authenticated encryption; no browser JWT storage."""
import json
import secrets
from threading import RLock
from cryptography.fernet import Fernet, InvalidToken
from .store import DomainError, digest


class AuthSessions:
    max_age = 30 * 86400

    def __init__(self, store, client, key):
        self.store, self.client, self.cipher = store, client, Fernet(key)
        self.lock = RLock()  # Single server process serializes refresh-token rotation.
        with store.transaction() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS auth_sessions (
                  id TEXT PRIMARY KEY, subject TEXT NOT NULL, ciphertext TEXT NOT NULL,
                  created_at REAL NOT NULL, last_seen REAL NOT NULL, kind TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sso_requests (
                  id TEXT PRIMARY KEY, state TEXT NOT NULL, expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_password_verifications (
                  session_id TEXT PRIMARY KEY REFERENCES auth_sessions(id), verified_at REAL NOT NULL);
            ''')

    def encrypt(self, data):
        return self.cipher.encrypt(json.dumps(data).encode()).decode()

    def decrypt(self, value):
        try:
            return json.loads(self.cipher.decrypt(value.encode()))
        except (InvalidToken, ValueError):
            raise DomainError('UNAUTHORIZED', 401) from None

    def create(self, tokens, kind='browser'):
        cookie = secrets.token_urlsafe(32)
        now = self.store.clock()
        with self.store.transaction() as db:
            db.execute('INSERT INTO auth_sessions VALUES (?,?,?,?,?,?)',
                       (digest(cookie), tokens['id'], self.encrypt(tokens), now, now, kind))
        return cookie

    def require(self, cookie):
        return self.require_hash(digest(cookie), kind='browser')

    def require_hash(self, session_id, kind=None):
        with self.lock:
            with self.store.transaction() as db:
                row = db.execute('SELECT * FROM auth_sessions WHERE id=?', (session_id,)).fetchone()
            if not row or self.store.clock() - row['last_seen'] > self.max_age:
                raise DomainError('UNAUTHORIZED', 401)
            if kind and row['kind'] != kind:
                raise DomainError('UNAUTHORIZED', 401)
            tokens = self.decrypt(row['ciphertext'])
            if tokens['expires_at'] <= self.store.clock() + 60:
                refreshed = self.client.refresh(tokens['refresh_token'])
                if refreshed['id'] != row['subject']:
                    raise DomainError('UNAUTHORIZED', 401)
                tokens = refreshed
            user = self.client.owner(tokens['access_token'])
            if user['id'] != row['subject']:
                raise DomainError('UNAUTHORIZED', 401)
            with self.store.transaction() as db:
                changed = db.execute('UPDATE auth_sessions SET ciphertext=?,last_seen=? WHERE id=?',
                                     (self.encrypt(tokens), self.store.clock(), session_id)).rowcount
            if not changed:
                raise DomainError('UNAUTHORIZED', 401)
            return {**user, 'session_id': session_id, 'tokens': tokens}

    def delete(self, cookie):
        with self.lock, self.store.transaction() as db:
            # The browser cookie becomes unusable. Already enrolled agents keep
            # the same canonical refresh session, avoiding refresh-token copies.
            db.execute("UPDATE auth_sessions SET kind='agent' WHERE id=?", (digest(cookie),))

    def delegate(self, principal):
        return principal['session_id']

    def password_verified(self, cookie):
        with self.store.transaction() as db:
            db.execute('INSERT OR REPLACE INTO auth_password_verifications VALUES (?,?)',
                       (digest(cookie), self.store.clock()))

    def consume_password_verification(self, session_id):
        with self.store.transaction() as db:
            row = db.execute('SELECT verified_at FROM auth_password_verifications WHERE session_id=?', (session_id,)).fetchone()
            if not row or self.store.clock() - row['verified_at'] > 600:
                raise DomainError('RECENT_OTP_REQUIRED', 403)
            db.execute('DELETE FROM auth_password_verifications WHERE session_id=?', (session_id,))

    def sso_start(self):
        cookie, state = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.store.transaction() as db:
            db.execute('DELETE FROM sso_requests WHERE expires_at<=?', (self.store.clock(),))
            db.execute('INSERT INTO sso_requests VALUES (?,?,?)',
                       (digest(cookie), state, self.store.clock() + 600))
        return cookie, state

    def sso_consume(self, cookie, state):
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM sso_requests WHERE id=?', (digest(cookie),)).fetchone()
            if not row or row['expires_at'] <= self.store.clock() or not secrets.compare_digest(row['state'], state):
                raise DomainError('SSO_STATE_INVALID', 400)
            db.execute('DELETE FROM sso_requests WHERE id=?', (row['id'],))
