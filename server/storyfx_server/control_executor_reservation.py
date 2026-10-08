"""Read dispatch eligibility under the same write transaction as reservation."""
import json
from .control_android import executors


def current_executors(db, owner, publication, now):
    nodes = []
    for row in db.execute('''SELECT n.id,n.profiles,n.last_seen,n.revoked,
      a.device_id,a.owner_id AS link_owner,a.profile,a.enabled,a.ready,
      d.owner_id AS device_owner,d.revoked AS device_revoked,
      COALESCE(m.ready,0) AS media_modes_ready
      FROM control_nodes n LEFT JOIN control_android_links a ON a.node_id=n.id
      LEFT JOIN devices d ON d.id=a.device_id
      LEFT JOIN control_android_media m ON m.device_id=a.device_id
      WHERE n.owner_id=?''', (owner,)):
        native = row['device_id'] is not None
        connected = not row['revoked'] and row['last_seen'] is not None and 0 <= now-row['last_seen'] < 45
        profiles = json.loads(row['profiles'])
        if native:
            connected = bool(connected and row['link_owner'] == owner and row['device_owner'] == owner
                             and row['device_revoked'] == 0 and row['enabled'] and row['ready']
                             and row['profile'] == publication['device'])
            # A secondary permission is never an executable WhatsApp binding.
            profiles = [row['profile']] if row['profile'] in profiles else []
        nodes.append({'id': row['id'], 'profiles': profiles, 'connected': connected,
                      'executor': 'android_whatsapp_images_v1' if native else 'windows_bridge',
                      'media_modes_ready': bool(row['media_modes_ready'])})
    return executors({'nodes': nodes}, publication)
