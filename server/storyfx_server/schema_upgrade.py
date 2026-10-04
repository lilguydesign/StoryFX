"""Additive ownership migration. Legacy diagnostic data is never adopted."""


def upgrade(db):
    columns = {
        'devices': {'owner_id': "TEXT NOT NULL DEFAULT 'validation_owner'", 'auth_session_hash': 'TEXT'},
        'pairings': {'owner_id': "TEXT NOT NULL DEFAULT 'validation_owner'", 'auth_session_hash': 'TEXT'},
    }
    for table, fields in columns.items():
        existing = {row['name'] for row in db.execute(f'PRAGMA table_info({table})')}
        for name, definition in fields.items():
            if name not in existing:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
    db.execute('CREATE INDEX IF NOT EXISTS devices_owner_id ON devices(owner_id)')
