"""Prevent simultaneous gestures from Windows and Android on the same phone."""
import json


def phone_busy(db, owner, profile):
    settings = {row['json_name']: json.loads(row['value']) for row in db.execute(
        "SELECT json_name,value FROM control_items WHERE owner_id=? AND collection='profiles'", (owner,))}
    current = settings.get(profile, {})
    hardware = current.get('adb_serial')
    for row in db.execute("SELECT payload FROM control_jobs WHERE owner_id=? AND state IN ('CLAIMED','CANCEL_REQUESTED')", (owner,)):
        other = json.loads(row['payload'])['device']
        if other == profile or hardware and settings.get(other, {}).get('adb_serial') == hardware:
            return True
    return False
