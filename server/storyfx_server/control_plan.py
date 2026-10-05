"""Deterministic scheduled occurrences. Nothing here launches a publication."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .store import fingerprint


def occurrence(row, due):
    fields = {key: row.get(key, '') for key in
              ('device', 'platform', 'system', 'engine', 'album', 'album2', 'count', 'page', 'page_name')}
    return fingerprint({'row': fields, 'due_at': due})


def plan(catalog, now):
    values = catalog['collections']
    profiles = {value['name']: value for value in values['profiles']}
    systems = {value['name']: value for value in values['systems']}
    zone = ZoneInfo('Africa/Douala')
    local = datetime.fromtimestamp(now, zone)
    day = local.replace(hour=0, minute=0, second=0, microsecond=0)
    result, seen = [], set()
    for row in values['matrix']:
        profile, system = profiles.get(row['device']), systems.get(row['system'])
        if not profile or not profile['enabled'] or not system:
            continue
        for clock in system['times']:
            hour, minute = map(int, clock.split(':'))
            shifted = (hour * 60 + minute + profile['offset_minutes']) % 1440
            due = day + timedelta(minutes=shifted)
            utc = due.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
            identity = occurrence(row, utc)
            if identity in seen:
                continue
            seen.add(identity)
            result.append({'id': identity, 'row_id': row['id'], 'due_at': utc,
                           'local_time': due.strftime('%H:%M'), 'due': due.timestamp() <= now,
                           **{key: row[key] for key in ('device', 'platform', 'system', 'engine', 'album', 'album2', 'count', 'page_name')}})
    return sorted(result, key=lambda value: (value['due_at'], value['device']))
