"""Server-side evidence needs no USB, credentials, network, executor or writable DB."""
import hashlib
import json
from pathlib import Path
import sqlite3
from storyfx_server.control_plan import plan
from storyfx_server.observation_runner import collect
from storyfx_server.publication_observation import read_snapshot


def fixture(folder):
    start = 1791340800
    config = {'owner_id': 'owner-a', 'start_unix': start, 'end_unix': start + 7 * 86400,
              'device_profiles': ['Validation technique'], 'schedule_profiles': ['Validation technique'],
              'whatsapp_forbidden_profiles': ['Other']}
    (folder / 'observation-config.json').write_text(json.dumps(config))
    db = sqlite3.connect(folder / 'storyfx.db')
    db.executescript('CREATE TABLE control_items(id,owner_id,collection,value);'
                    'CREATE TABLE control_schedulers(owner_id,enabled,scope,wait_reason);'
                    'CREATE TABLE control_jobs(id,owner_id,occurrence,state,payload,evidence,created);'
                    'CREATE TABLE control_android_links(device_id,owner_id,profile,enabled,ready,reason);'
                    'CREATE TABLE devices(id,last_seen,revoked,app_version);')
    values = {'profiles': [{'name': 'Validation technique', 'enabled': True, 'offset_minutes': 0}],
              'systems': [{'name': 'Validation technique', 'times': ['04:00']}],
              'matrix': [{'id': 'row', 'device': 'Validation technique', 'platform': 'WhatsApp',
                          'system': 'Validation technique', 'engine': 'multi', 'count': 9,
                          'album': 'Validation technique', 'album2': '', 'page_name': ''}]}
    for collection, rows in values.items():
        for row in rows:
            db.execute('INSERT INTO control_items VALUES (?,?,?,?)', (row.get('id', collection), 'owner-a', collection, json.dumps(row)))
    db.execute('INSERT INTO control_schedulers VALUES (?,1,?,?)',
               ('owner-a', json.dumps({'profiles': ['Validation technique'], 'platforms': ['WhatsApp']}), ''))
    db.execute('INSERT INTO devices VALUES (?,?,0,?)', ('device', start, 'synthetic'))
    db.execute('INSERT INTO control_android_links VALUES (?,?,?,0,0,?)', ('device', 'owner-a', 'Validation technique', 'DISABLED'))
    db.commit()
    return db, config, values


def test_no_usb_and_no_database_mutation(tmp_path):
    db, config, values = fixture(tmp_path)
    occurrence = plan({'collections': values}, config['start_unix'])[0]['id']
    for owner, state, depth in [('owner-b', 'CONFIRMED', 8), ('owner-a', 'NEEDS_REVIEW', 0), ('owner-a', 'CONFIRMED', 1)]:
        payload = {'original_occurrence': occurrence, 'retry_depth': depth}
        db.execute('INSERT INTO control_jobs VALUES (?,?,?,?,?,?,?)', (str(depth) + owner, owner, str(depth), state,
                    json.dumps(payload), 'own_status_verified', depth))
    db.commit(); db.close()
    before = hashlib.sha256((tmp_path / 'storyfx.db').read_bytes()).hexdigest()
    result = read_snapshot(tmp_path / 'storyfx.db', config, config['start_unix'] + 3600)
    assert result['totals'] == {'confirmed_agent': 1}
    assert result['rows'][0]['expected_count'] == 9 and result['rows'][0]['retry_depth'] == 1
    assert not result['devices'][0]['publication_enabled']
    assert before == hashlib.sha256((tmp_path / 'storyfx.db').read_bytes()).hexdigest()


def test_multiple_days_and_no_replay_or_false_facebook_confirmation(tmp_path):
    db, config, _ = fixture(tmp_path)
    value = json.loads(db.execute("SELECT value FROM control_items WHERE collection='matrix'").fetchone()[0])
    value['platform'] = 'Facebook'; value['page_name'] = 'Validation technique'
    db.execute("UPDATE control_items SET value=? WHERE collection='matrix'", (json.dumps(value),))
    db.commit(); db.close()
    result = read_snapshot(tmp_path / 'storyfx.db', config, config['start_unix'] + 2 * 86400)
    assert len(result['rows']) == 2
    assert all(r['verdict'] == 'adapter_not_validated' and not r['facebook_page_and_batch_verified'] for r in result['rows'])
    assert not result['total_autonomy_verified'] and not result['real_send_triggered_by_observer']


def test_runner_idempotence_bounded_end_and_private_state(tmp_path):
    db, config, _ = fixture(tmp_path); db.close()
    first = collect(tmp_path, config['start_unix'] + 3600)
    assert not first['complete']
    collect(tmp_path, config['start_unix'] + 3601)
    assert len(json.loads((tmp_path / 'observation-state.json').read_text())['observations']) == 1
    assert collect(tmp_path, config['end_unix'] + 900)['complete']
    assert (tmp_path / 'observation-complete').exists()
    before = (tmp_path / 'observation-state.json').read_bytes()
    collect(tmp_path, config['end_unix'] + 3600)
    assert (tmp_path / 'observation-state.json').read_bytes() == before
