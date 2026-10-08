"""Re-read native channel identity inside broker transactions; receipts stay immutable."""
import json
from .store import DomainError
from .control_media_modes import requires_media_v2


def guard_job(db, node, row, now, *, receipt=False):
    native = db.execute('''SELECT a.profile,a.enabled,a.ready,a.owner_id,n.revoked,n.last_seen,
      d.owner_id AS device_owner,d.revoked AS device_revoked,COALESCE(m.ready,0) AS media_ready FROM control_android_links a
      JOIN control_nodes n ON n.id=a.node_id AND n.owner_id=a.owner_id
      JOIN devices d ON d.id=a.device_id LEFT JOIN control_android_media m ON m.device_id=a.device_id
      WHERE a.node_id=?''', (node['id'],)).fetchone()
    if native is None:
        if 'enabled' in node:
            raise DomainError('ANDROID_PROFILE_BINDING_CHANGED', 409)
        return  # Existing Windows provider proof/routing is a distinct contract.
    payload = json.loads(row['payload'])
    if payload.get('platform') != 'WhatsApp':
        raise DomainError('ADAPTER_NOT_VALIDATED' if not receipt else 'ANDROID_RESULT_INVALID', 422 if receipt else 409)
    if receipt:
        return  # A late/final receipt does not depend on current enable/readiness/profile state.
    if (native['owner_id'] != node['owner_id'] or native['device_owner'] != node['owner_id']
            or native['revoked'] or native['device_revoked'] or native['profile'] != payload.get('device')):
        raise DomainError('ANDROID_PROFILE_BINDING_CHANGED', 409)
    if (not native['enabled'] or not native['ready'] or native['last_seen'] is None
            or not 0 <= now - native['last_seen'] < 45):
        raise DomainError('ANDROID_EXECUTOR_NOT_READY', 409)
    if requires_media_v2(payload) and not native['media_ready']:
        raise DomainError('ANDROID_MEDIA_PERMISSION_REQUIRED', 409)
