"""Owner-isolated settings, revision checks and a private one-time legacy seed."""
import json
from pathlib import Path
from uuid import uuid4
from pydantic import ValidationError
from .control_models import MODELS
from .store import DomainError, timestamp


class Catalog:
    def __init__(self, store):
        self.store = store
        with store.transaction() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS control_owners (
                  owner_id TEXT PRIMARY KEY, revision INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS control_items (
                  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, collection TEXT NOT NULL,
                  value TEXT NOT NULL, json_name TEXT NOT NULL,
                  UNIQUE(owner_id,collection,json_name));
            ''')

    def ensure(self, user):
        with self.store.transaction() as db:
            current = db.execute('SELECT revision FROM control_owners WHERE owner_id=?', (user['id'],)).fetchone()
            if current and current[0] > 0:
                return
            if not current:
                db.execute('INSERT INTO control_owners VALUES (?,0)', (user['id'],))
            path = self.store.path.parent / 'control-seed.json'
            if not path.is_file():
                return
            seed = json.loads(path.read_text(encoding='utf-8-sig'))
            if seed.get('owner_email', '').casefold() != user.get('email', '').casefold():
                return
            for collection, values in seed.get('collections', {}).items():
                if collection not in MODELS or not isinstance(values, list) or len(values) > 500:
                    raise DomainError('PRIVATE_SEED_INVALID', 503)
                for value in values:
                    clean = self.validate(collection, value)
                    db.execute('INSERT INTO control_items VALUES (?,?,?,?,?)',
                               (str(uuid4()), user['id'], collection, json.dumps(clean), clean['name']))
            db.execute('UPDATE control_owners SET revision=1 WHERE owner_id=?', (user['id'],))

    @staticmethod
    def validate(collection, value):
        if collection not in MODELS:
            raise DomainError('COLLECTION_NOT_FOUND', 404)
        try:
            return MODELS[collection].model_validate(value).model_dump()
        except (ValidationError, ValueError):
            raise DomainError('INVALID_SETTING', 422) from None

    def read(self, user):
        self.ensure(user)
        with self.store.transaction() as db:
            revision = db.execute('SELECT revision FROM control_owners WHERE owner_id=?', (user['id'],)).fetchone()[0]
            values = {name: [] for name in MODELS}
            for row in db.execute('SELECT * FROM control_items WHERE owner_id=? ORDER BY collection,json_name', (user['id'],)):
                values[row['collection']].append({'id': row['id'], **json.loads(row['value'])})
        return {'revision': revision, 'collections': values, 'timezone': 'Africa/Douala',
                'server_time': timestamp(self.store.clock()), 'automatic_publication_enabled': False}

    @staticmethod
    def revision(db, owner, expected):
        row = db.execute('SELECT revision FROM control_owners WHERE owner_id=?', (owner,)).fetchone()
        if row is None or row[0] != expected:
            raise DomainError('CONFIGURATION_CHANGED', 409)

    def write(self, user, collection, change, item_id=None):
        self.ensure(user)
        clean = self.validate(collection, change.value)
        with self.store.transaction() as db:
            self.revision(db, user['id'], change.revision)
            existing = db.execute('SELECT * FROM control_items WHERE owner_id=? AND collection=? AND id=?',
                                  (user['id'], collection, item_id)).fetchone() if item_id else None
            if item_id and not existing:
                raise DomainError('SETTING_NOT_FOUND', 404)
            duplicate = db.execute('SELECT id FROM control_items WHERE owner_id=? AND collection=? AND json_name=?',
                                   (user['id'], collection, clean['name'])).fetchone()
            if duplicate and duplicate[0] != item_id:
                raise DomainError('NAME_ALREADY_EXISTS', 409)
            if existing and json.loads(existing['value'])['name'] != clean['name']:
                self.references(db, user['id'], collection, json.loads(existing['value'])['name'])
            if collection == 'matrix':
                for member, target in [('device', 'profiles'), ('system', 'systems'), ('album', 'albums'), ('album2', 'albums')]:
                    if clean[member] and not db.execute('SELECT 1 FROM control_items WHERE owner_id=? AND collection=? AND json_name=?',
                                                       (user['id'], target, clean[member])).fetchone():
                        raise DomainError('SETTING_REFERENCE_MISSING', 422)
                if not (clean['album'] if clean['engine'] == 'intro' else clean['album2'] or clean['album']):
                    raise DomainError('ALBUM_REQUIRED', 422)
            if not existing and db.execute('SELECT COUNT(*) FROM control_items WHERE owner_id=? AND collection=?',
                                           (user['id'], collection)).fetchone()[0] >= 500:
                raise DomainError('SETTING_LIMIT', 409)
            selected = item_id or str(uuid4())
            if existing:
                db.execute('UPDATE control_items SET value=?,json_name=? WHERE id=?', (json.dumps(clean), clean['name'], selected))
            else:
                db.execute('INSERT INTO control_items VALUES (?,?,?,?,?)', (selected, user['id'], collection, json.dumps(clean), clean['name']))
            db.execute('UPDATE control_owners SET revision=revision+1 WHERE owner_id=?', (user['id'],))
        return self.read(user)

    @staticmethod
    def references(db, owner, collection, name):
        fields = {'profiles': ['device'], 'systems': ['system'], 'albums': ['album', 'album2'], 'pages': ['page_name']}.get(collection, [])
        for row in db.execute("SELECT value FROM control_items WHERE owner_id=? AND collection='matrix'", (owner,)):
            value = json.loads(row[0])
            if any(value.get(field) == name for field in fields):
                raise DomainError('SETTING_IN_USE', 409)

    def remove(self, user, collection, item_id, revision):
        self.ensure(user)
        with self.store.transaction() as db:
            self.revision(db, user['id'], revision)
            row = db.execute('SELECT json_name FROM control_items WHERE owner_id=? AND collection=? AND id=?',
                             (user['id'], collection, item_id)).fetchone()
            if not row:
                raise DomainError('SETTING_NOT_FOUND', 404)
            self.references(db, user['id'], collection, row[0])
            db.execute('DELETE FROM control_items WHERE id=?', (item_id,))
            db.execute('UPDATE control_owners SET revision=revision+1 WHERE owner_id=?', (user['id'],))
        return self.read(user)
