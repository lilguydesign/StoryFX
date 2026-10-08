"""Owner-created immutable validation plans; lifecycle actions never enqueue jobs."""
import json
from uuid import uuid4
from .control_media_modes import supported_media
from .control_recipe_state import (initialize, active_recipe, boundary, get_recipe,
                                  pending_count, recipe_view)
from .store import DomainError, fingerprint, timestamp


class Recipes:
    def __init__(self, broker):
        self.broker, self.store = broker, broker.store
        initialize(self.store)

    def list(self, user):
        with self.store.transaction() as db:
            rows = db.execute('SELECT * FROM control_recipes WHERE owner_id=? ORDER BY created DESC,id LIMIT 100',
                              (user['id'],)).fetchall()
            held = active_recipe(db, user['id'])
            if held and not any(row['id'] == held for row in rows):
                rows.insert(0, get_recipe(db, user['id'], held))
            return {'recipes': [recipe_view(db, row, self.store.clock()) for row in rows],
                    'active_recipe_id': held}

    def read(self, user, identity):
        with self.store.transaction() as db:
            return recipe_view(db, get_recipe(db, user['id'], identity), self.store.clock())

    def create(self, user, body):
        request_hash = fingerprint(body.model_dump(mode='json', exclude={'client_key'}))
        key = str(body.client_key)
        with self.store.transaction() as db:
            prior = db.execute('SELECT * FROM control_recipes WHERE owner_id=? AND client_key=?',
                               (user['id'], key)).fetchone()
            if prior:
                if prior['request_hash'] != request_hash:
                    raise DomainError('RECIPE_IDEMPOTENCY_CONFLICT', 409)
                return recipe_view(db, prior, self.store.clock())
        catalog = self.broker.catalog.read(user)
        if catalog['revision'] != body.revision:
            raise DomainError('CONFIGURATION_CHANGED', 409)
        profiles = {p['name']: p for p in catalog['collections']['profiles']}
        available = {r['id']: r for r in catalog['collections']['matrix']}
        selected = []
        for identity in body.row_ids:
            value = available.get(str(identity))
            if not value:
                raise DomainError('RECIPE_ROW_NOT_FOUND', 404)
            if not supported_media(value):
                raise DomainError('ADAPTER_NOT_VALIDATED', 409)
            if not profiles.get(value['device'], {}).get('enabled', False):
                raise DomainError('PROFILE_NOT_FOUND', 422)
            selected.append(value)
        with self.store.transaction() as db:
            prior = db.execute('SELECT * FROM control_recipes WHERE owner_id=? AND client_key=?',
                               (user['id'], key)).fetchone()
            if prior:
                if prior['request_hash'] != request_hash:
                    raise DomainError('RECIPE_IDEMPOTENCY_CONFLICT', 409)
                return recipe_view(db, prior, self.store.clock())
            self.broker.catalog.revision(db, user['id'], body.revision)
            identity = str(uuid4())
            db.execute('INSERT INTO control_recipes VALUES (?,?,?,?,?,?,?, ?,NULL,NULL,NULL)',
                       (identity, user['id'], key, request_hash, body.revision, 'android', 'DRAFT', self.store.clock()))
            for position, value in enumerate(selected, start=1):
                db.execute('INSERT INTO control_recipe_steps VALUES (?,?,?,?,?,NULL,NULL)',
                           (str(uuid4()), identity, position, value['id'], json.dumps(value)))
            return recipe_view(db, get_recipe(db, user['id'], identity), self.store.clock())

    def start(self, user, identity):
        with self.store.transaction() as db:
            row = get_recipe(db, user['id'], identity)
            held = active_recipe(db, user['id'])
            if held == identity:
                return recipe_view(db, row, self.store.clock())
            if row['state'] != 'DRAFT':
                raise DomainError('RECIPE_STATE_INVALID', 409)
            if held:
                raise DomainError('MANUAL_RECIPE_ACTIVE', 409)
            self.broker.catalog.revision(db, user['id'], row['revision'])
            scheduler = db.execute('SELECT * FROM control_schedulers WHERE owner_id=?', (user['id'],)).fetchone()
            before = ({'enabled': bool(scheduler['enabled']), 'mode': scheduler['mode'],
                       **json.loads(scheduler['scope']), 'from_at': timestamp(scheduler['from_at'])}
                      if scheduler else {'enabled': False, 'mode': 'auto', 'profiles': [], 'platforms': [], 'from_at': None})
            db.execute('INSERT INTO control_recipe_locks VALUES (?,?)', (user['id'], identity))
            db.execute("UPDATE control_recipes SET state='ACTIVE',started=?,scheduler_before=? WHERE id=?",
                       (self.store.clock(), json.dumps(before), identity))
            db.execute('INSERT INTO control_recipe_boundaries VALUES (?,0,0) ON CONFLICT(owner_id) '
                       'DO UPDATE SET automation_ready=0', (user['id'],))
            return recipe_view(db, get_recipe(db, user['id'], identity), self.store.clock())

    def cancel(self, user, identity):
        with self.store.transaction() as db:
            row = get_recipe(db, user['id'], identity)
            if row['state'] == 'RELEASED':
                raise DomainError('RECIPE_STATE_INVALID', 409)
            db.execute("UPDATE control_recipes SET state='CANCELLED' WHERE id=?", (identity,))
            # Keep the lock until every pre-existing or recipe attempt has a receipt.
            return recipe_view(db, get_recipe(db, user['id'], identity), self.store.clock())

    def release(self, user, identity):
        with self.store.transaction() as db:
            row = get_recipe(db, user['id'], identity)
            if row['state'] == 'RELEASED':
                return recipe_view(db, row, self.store.clock())
            held = active_recipe(db, user['id']) == identity
            view = recipe_view(db, row, self.store.clock())
            if view['state'] not in ('PASSED', 'CANCELLED'):
                raise DomainError('RECIPE_RELEASE_REQUIRES_CANCEL_OR_PASS', 409)
            if held and pending_count(db, user['id']):
                raise DomainError('RECIPE_DRAINING', 409)
            if held:
                limit = boundary(db, user['id'])
                future = max(self.store.clock(), limit['not_before'] if limit else 0)
                if view['all_steps_verified']:
                    from datetime import datetime
                    future = max(future, max(datetime.fromisoformat(s['completed_at']).timestamp() + 300 for s in view['steps']))
                    db.execute('INSERT INTO control_recipe_validation VALUES (?,?,?,?) ON CONFLICT(owner_id) '
                               'DO UPDATE SET recipe_id=excluded.recipe_id,revision=excluded.revision,row_ids=excluded.row_ids',
                               (user['id'], identity, row['revision'], json.dumps([s['row_id'] for s in view['steps']])))
                db.execute('UPDATE control_recipe_boundaries SET not_before=?,automation_ready=? WHERE owner_id=?',
                           (future, int(view['all_steps_verified']), user['id']))
                # Retain scope, generation and definitions; resumption requires an explicit action.
                db.execute('UPDATE control_schedulers SET enabled=0 WHERE owner_id=?', (user['id'],))
                db.execute('DELETE FROM control_recipe_locks WHERE owner_id=? AND recipe_id=?', (user['id'], identity))
            db.execute("UPDATE control_recipes SET state='RELEASED',released=? WHERE id=?", (self.store.clock(), identity))
            return recipe_view(db, get_recipe(db, user['id'], identity), self.store.clock())

    def launch(self, user, identity, step_id, client_key):
        from .control_recipe_launch import launch_step
        return launch_step(self, user, identity, step_id, client_key)
