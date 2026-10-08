"""Synthetic association fixtures; no native device or network dependency."""
import json
from uuid import uuid4
from test_control_android import setup
from test_control_center import HEADERS, add

ROOT = '/v1/control/android/profile-bindings'


def fixture(private):
    app, browser, provider, now, auth, contact, device = setup(private)
    for index in (2, 3, 4):
        add(browser, 'profiles', name='Validation technique ' + str(index), adb_serial='synthetic-shared-hardware')
    snapshot = browser.get('/v1/control').json()
    profile = next(row for row in snapshot['collections']['profiles'] if row['name'] == 'Validation technique 2')
    body = {'client_key': str(uuid4()), 'revision': snapshot['revision'], 'device_id': device,
            'profile_id': profile['id'], 'platform': 'Facebook'}
    contact = {**contact, 'app_version': '0.4.15', 'media_modes_ready': True}
    browser.post('/v1/control/android/heartbeat', headers=auth, json=contact)
    return app, browser, provider, now, auth, contact, body


def associate(browser, body):
    return browser.post(ROOT, headers=HEADERS, json=body)


def remove(browser, binding, revision):
    return browser.post(ROOT + '/' + binding['id'] + '/remove', headers=HEADERS, json={'revision': revision})


def internals(app):
    with app.state.store.transaction() as db:
        return {table: [dict(row) for row in db.execute('SELECT * FROM ' + table)] for table in
                ('control_android_links', 'control_nodes', 'control_jobs', 'control_schedulers')}


def pending(app, body, state):
    identity = str(uuid4())
    with app.state.store.transaction() as db:
        link = db.execute('SELECT * FROM control_android_links WHERE device_id=?', (body['device_id'],)).fetchone()
        row = db.execute("SELECT value FROM control_items WHERE owner_id=? AND collection='matrix' LIMIT 1", (link['owner_id'],)).fetchone()
        payload = {**json.loads(row['value']), 'catalog_revision': body['revision'],
                   'due_at': '2023-11-14T05:00:00+00:00', 'execution_origin': 'web_android_agent', 'web_triggered': True}
        db.execute('INSERT INTO control_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (identity, link['owner_id'], link['node_id'], uuid4().hex * 2, json.dumps(payload), state,
                    app.state.store.clock(), app.state.store.clock(), None, None))
    return identity
