"""Physical agent availability is independent of a WhatsApp publication binding."""
import json
from pydantic import Field, StrictBool
from .control_models import Strict
from .store import DomainError


class NativeRuntime(Strict):
    contract_version: int = Field(strict=True, ge=1, le=1)
    global_enabled: StrictBool
    service_ready: StrictBool
    accessibility_enabled: StrictBool
    screen_unlocked: StrictBool
    media_permission: StrictBool


def initialize(store):
    with store.transaction() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS control_native_runtime (
          device_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, node_id TEXT NOT NULL,
          auth_session_hash TEXT NOT NULL, observed REAL NOT NULL,
          app_version TEXT NOT NULL, value TEXT NOT NULL)''')


def check_contact(body):
    value = body.native_runtime
    if value is not None and (value.service_ready != body.service_ready
            or value.screen_unlocked == body.screen_locked or value.media_permission != body.media_ready
            or value.service_ready and not value.accessibility_enabled):
        raise DomainError('NATIVE_RUNTIME_INCOHERENT', 422)


def record(db, identity, node, body, now):
    if body.native_runtime is None:
        # A downgraded/legacy agent cannot renew an earlier physical readiness assertion.
        db.execute('DELETE FROM control_native_runtime WHERE device_id=? AND owner_id=?',
                   (identity.id, identity.owner_id))
        return
    db.execute('''INSERT INTO control_native_runtime VALUES (?,?,?,?,?,?,?)
      ON CONFLICT(device_id) DO UPDATE SET owner_id=excluded.owner_id,node_id=excluded.node_id,
      auth_session_hash=excluded.auth_session_hash,observed=excluded.observed,
      app_version=excluded.app_version,value=excluded.value''',
      (identity.id, identity.owner_id, node['id'], identity.auth_session_hash, now, body.app_version,
       json.dumps(body.native_runtime.model_dump())))


def availability(db, owner, device, node, now):
    row = db.execute('''SELECT r.* FROM control_native_runtime r
      JOIN devices d ON d.id=r.device_id AND d.owner_id=r.owner_id AND d.revoked=0
      JOIN control_nodes n ON n.id=r.node_id AND n.owner_id=r.owner_id AND n.revoked=0
      JOIN control_android_links a ON a.device_id=r.device_id AND a.node_id=r.node_id AND a.owner_id=r.owner_id
      WHERE r.owner_id=? AND r.device_id=? AND r.node_id=?
      AND r.auth_session_hash=d.auth_session_hash AND r.auth_session_hash=n.auth_session
      AND r.app_version=d.app_version''', (owner, device, node)).fetchone()
    reason, reported = 'NATIVE_RUNTIME_UNREPORTED', row is not None
    if row is not None:
        value = NativeRuntime.model_validate_json(row['value'])
        reason = ('NATIVE_RUNTIME_STALE' if not 0 <= now - row['observed'] < 45 else
                  'GLOBAL_AGENT_DISABLED' if not value.global_enabled else
                  'ACCESSIBILITY_REQUIRED' if not value.accessibility_enabled or not value.service_ready else
                  'SCREEN_LOCKED' if not value.screen_unlocked else
                  'MEDIA_PERMISSION_REQUIRED' if not value.media_permission else '')
    return {'contract_version': 1, 'reported': reported, 'physical_ready': not reason,
            'reason': reason, 'publication_authorized': False}
