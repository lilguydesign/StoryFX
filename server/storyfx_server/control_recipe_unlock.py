"""Read-only, short permission for the first step of an explicitly started recipe."""
from .control_media_modes import supported_media, requires_media_v2
from .control_recipe_state import active_recipe, get_recipe, recipe_view
from .control_sequential_proof import compatible_version


def manual_unlock(db, owner, profile, node, device, snapshot, now):
    identity = active_recipe(db, owner)
    if not identity:
        return None
    row = get_recipe(db, owner, identity)
    if (row['state'] != 'ACTIVE' or row['executor'] != 'android'
            or row['revision'] != snapshot['revision'] or row['started'] is None
            or not 0 <= now - row['started'] < 90
            or not compatible_version(device['app_version'])):
        return False
    if db.execute('SELECT 1 FROM android_installation_holds WHERE owner_id=? AND released IS NULL',
                  (owner,)).fetchone():
        return False
    if db.execute('SELECT 1 FROM control_schedulers WHERE owner_id=? AND enabled=1', (owner,)).fetchone():
        return False
    if db.execute("SELECT 1 FROM control_jobs WHERE owner_id=? AND completed IS NULL", (owner,)).fetchone():
        return False
    if db.execute("SELECT 1 FROM jobs JOIN devices ON jobs.device_id=devices.id WHERE devices.owner_id=? "
                  "AND jobs.status IN ('QUEUED','CLAIMED','STARTED','NEEDS_REVIEW')", (owner,)).fetchone():
        return False
    view = recipe_view(db, row, now)
    if (view['state'] != 'READY' or not view['steps']
            or any(step['job_id'] for step in view['steps'])):
        return False
    first = view['steps'][0]
    publication = first['publication']
    return bool(first['id'] == view['next_step_id'] and publication['device'] == profile
                and supported_media(publication)
                and (not requires_media_v2(publication) or node['media_modes_ready']))
