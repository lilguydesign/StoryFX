"""Fresh native proof of an entirely empty own-status area, never provider contents."""
import json


def record(db, node, empty, ready, now):
    if (not empty or not ready or db.execute("SELECT 1 FROM control_jobs WHERE node_id=? AND state IN ('CLAIMED','CANCEL_REQUESTED')",
                                            (node['id'],)).fetchone()):
        db.execute('DELETE FROM control_status_reviews WHERE node_id=?', (node['id'],))
        return
    link = db.execute('SELECT profile FROM control_android_links WHERE node_id=? AND owner_id=?',
                      (node['id'], node['owner_id'])).fetchone()
    if link:
        db.execute('INSERT INTO control_status_reviews VALUES (?,?,?,?) ON CONFLICT(node_id) '
                   'DO UPDATE SET owner_id=excluded.owner_id,profile=excluded.profile,observed=excluded.observed',
                   (node['id'], node['owner_id'], link['profile'], now))


def empty_review(db, parent, now):
    # share_selection_refused is recorded only before the first provider send arrow.
    # It still requires a fresh entirely empty own-status observation; never replay uncertain results.
    payload = json.loads(parent['payload'])
    if (parent['state'] != 'FAILED_BEFORE_PUBLICATION' or parent['evidence'] not in {'preflight_refused', 'share_selection_refused'}
            or payload.get('execution_origin') != 'web_android_agent' or parent['claimed'] is None
            or not 0 <= now-parent['claimed'] < 23*3600):
        return False
    row = db.execute('SELECT observed,profile FROM control_status_reviews WHERE node_id=? AND owner_id=?',
                     (parent['node_id'], parent['owner_id'])).fetchone()
    if (not row or parent['completed'] is None or row['observed'] < parent['completed']
            or row['profile'] != payload.get('device') or not 0 <= now-row['observed'] < 45):
        return False
    return not db.execute("SELECT 1 FROM control_jobs WHERE node_id=? AND state IN ('CLAIMED','CANCEL_REQUESTED')",
                          (parent['node_id'],)).fetchone()
