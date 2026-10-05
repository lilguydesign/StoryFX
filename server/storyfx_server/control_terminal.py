"""Structured owner-private activity. Clearing hides lines, retaining the audit."""
from datetime import datetime
from zoneinfo import ZoneInfo


class Terminal:
    def __init__(self, store):
        self.store = store
        with store.transaction() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS control_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id TEXT NOT NULL,
                created REAL NOT NULL, kind TEXT NOT NULL, profile TEXT, system TEXT);
              CREATE TABLE IF NOT EXISTS control_terminal_cursors (
                owner_id TEXT PRIMARY KEY, cleared_through INTEGER NOT NULL DEFAULT 0);
            ''')

    def emit(self, db, owner, kind, profile='', system=''):
        db.execute('INSERT INTO control_events(owner_id,created,kind,profile,system) VALUES (?,?,?,?,?)',
                   (owner, self.store.clock(), kind, profile, system))

    def read(self, user):
        with self.store.transaction() as db:
            cursor = db.execute('SELECT cleared_through FROM control_terminal_cursors WHERE owner_id=?', (user['id'],)).fetchone()
            rows = db.execute('SELECT * FROM control_events WHERE owner_id=? AND id>? ORDER BY id DESC LIMIT 200',
                              (user['id'], cursor[0] if cursor else 0)).fetchall()
        return [{'id':row['id'], 'time':datetime.fromtimestamp(row['created'], ZoneInfo('Africa/Douala')).isoformat(),
                 'kind':row['kind'], 'profile':row['profile'], 'system':row['system']} for row in reversed(rows)]

    def clear(self, user):
        with self.store.transaction() as db:
            last = db.execute('SELECT COALESCE(MAX(id),0) FROM control_events WHERE owner_id=?', (user['id'],)).fetchone()[0]
            db.execute('INSERT INTO control_terminal_cursors VALUES (?,?) ON CONFLICT(owner_id) DO UPDATE SET cleared_through=excluded.cleared_through',
                       (user['id'], last))
        return {'cleared':True, 'audit_preserved':True}
