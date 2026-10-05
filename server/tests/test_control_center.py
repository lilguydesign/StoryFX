"""Settings isolation and one-attempt publications using only synthetic executors."""
import json
import secrets
import pytest
from test_private_auth import private, login, ORIGIN

HEADERS = {'Origin': ORIGIN}


def add(browser, collection, **value):
    revision = browser.get('/v1/control').json()['revision']
    response = browser.post('/v1/control/settings/' + collection, headers=HEADERS,
                            json={'revision': revision, 'value': value})
    assert response.status_code == 200, response.text
    return response.json()


def settings(browser):
    add(browser, 'profiles', name='Validation technique', offset_minutes=40)
    add(browser, 'albums', name='Validation technique', count_per_post=3)
    add(browser, 'systems', name='Validation technique', times=['06:00', '12:00'])
    return add(browser, 'matrix', name='Validation technique', device='Validation technique',
               platform='WhatsApp', system='Validation technique', engine='multi', album2='Validation technique', count=3)


def executor(browser):
    proof = secrets.token_urlsafe(32)
    identity = browser.post('/v1/control/windows/start', json={'name': 'Validation technique', 'proof': proof}).json()['request_id']
    assert browser.post('/v1/control/windows/poll', json={'request_id': identity, 'proof': proof}).json() == {'pending': True}
    assert browser.post('/v1/control/windows/approve', headers=HEADERS, json={'request_id': identity}).status_code == 200
    result = browser.post('/v1/control/windows/poll', json={'request_id': identity, 'proof': proof}).json()
    assert browser.post('/v1/control/windows/poll', json={'request_id': identity, 'proof': proof}).status_code == 409
    return {'Authorization': 'Bearer ' + result['credential']}


def test_owner_isolation_closed_settings_and_revision(private):
    _, browser, _, _ = private
    assert browser.get('/v1/control').status_code == 401
    login(browser)
    settings(browser)
    snapshot = browser.get('/v1/control').json()
    assert len(snapshot['schedule']) == 2
    assert {value['local_time'] for value in snapshot['schedule']} == {'06:40', '12:40'}
    revision = snapshot['revision']
    invalid = {'name': 'Validation technique 2', 'arbitrary_command': 'synthetic-private-identity'}
    response = browser.post('/v1/control/settings/profiles', headers=HEADERS, json={'revision': revision, 'value': invalid})
    assert response.status_code == 422 and invalid['arbitrary_command'] not in response.text
    assert browser.post('/v1/control/settings/profiles', json={'revision': revision, 'value': {'name': 'Validation technique 2'}}).status_code == 403
    assert browser.post('/v1/control/settings/profiles', headers=HEADERS, json={'revision': revision-1, 'value': {'name': 'Validation technique 2'}}).status_code == 409
    item = snapshot['collections']['profiles'][0]
    assert browser.post('/v1/control/settings/profiles/' + item['id'] + '/remove', headers=HEADERS, json={'revision': revision}).status_code == 409
    login(browser, 'owner-b')
    assert browser.get('/v1/control').json()['collections']['profiles'] == []
    assert browser.put('/v1/control/settings/profiles/' + item['id'], headers=HEADERS, json={'revision': 0, 'value': {'name': 'Validation technique'}}).status_code == 404


def test_bridge_one_claim_and_no_replay_of_ambiguous_publication(private):
    _, browser, provider, now = private
    login(browser)
    settings(browser)
    before = browser.get('/v1/control').json()
    launch = {'occurrence_id': before['schedule'][0]['id'], 'revision': before['revision']}
    assert browser.post('/v1/control/launch', headers=HEADERS, json=launch).status_code == 409
    auth = executor(browser)
    assert browser.post('/v1/control/windows/heartbeat', headers=auth, json={'profiles': ['Validation technique']}).status_code == 200
    accepted = browser.post('/v1/control/launch', headers=HEADERS, json=launch)
    assert accepted.status_code == 200
    assert browser.post('/v1/control/launch', headers=HEADERS, json=launch).status_code == 409
    # Move beyond today's planned time without changing the day.
    from datetime import datetime
    now[0] = max(now[0], datetime.fromisoformat(before['schedule'][0]['due_at'].replace('Z', '+00:00')).timestamp() + 1)
    job = browser.post('/v1/control/windows/claim', headers=auth, json={}).json()['job']
    assert job is not None
    assert browser.post('/v1/control/windows/claim', headers=auth, json={}).json()['job'] is None
    now[0] += 901
    snapshot = browser.get('/v1/control').json()
    assert snapshot['reports'][0]['state'] == 'NEEDS_REVIEW'
    assert browser.post('/v1/control/windows/claim', headers=auth, json={}).json()['job'] is None
    assert browser.post('/v1/control/launch', headers=HEADERS, json=launch).status_code == 409
    provider.denied.add('owner-a')
    assert browser.post('/v1/control/windows/heartbeat', headers=auth, json={'profiles': []}).status_code == 403


def test_pair_proof_expiry_and_cross_owner_results(private):
    _, browser, _, now = private
    login(browser)
    proof = secrets.token_urlsafe(32)
    identity = browser.post('/v1/control/windows/start', json={'name': 'Validation technique', 'proof': proof}).json()['request_id']
    assert browser.post('/v1/control/windows/poll', json={'request_id': identity, 'proof': secrets.token_urlsafe(32)}).status_code == 409
    assert browser.post('/v1/control/windows/approve', json={'request_id': identity}).status_code == 403
    now[0] += 601
    assert browser.post('/v1/control/windows/approve', headers=HEADERS, json={'request_id': identity}).status_code == 409


def test_private_seed_is_owner_bound_and_imports_confirmed_occurrence(private):
    app, browser, _, _ = private
    seed = {'owner_email': 'owner-a@example.invalid', 'collections': {
        'profiles': [{'name': 'Validation technique', 'offset_minutes': 40}],
        'albums': [{'name': 'Validation technique', 'count_per_post': 3}],
        'systems': [{'name': 'Validation technique', 'times': ['06:00']}],
        'matrix': [{'name': 'Validation technique', 'device': 'Validation technique', 'platform': 'WhatsApp',
                    'system': 'Validation technique', 'engine': 'multi', 'album2': 'Validation technique', 'count': 3}]},
        'confirmed_publications': [{'profile': 'Validation technique', 'system': 'Validation technique',
                                   'scheduled_at': '2023-11-14T05:40:00Z', 'confirmed_media_count': 3,
                                   'provider_evidence': 'own_status_three_just_now'}]}
    (app.state.store.path.parent / 'control-seed.json').write_text(json.dumps(seed))
    login(browser, 'owner-b')
    assert browser.get('/v1/control').json()['collections']['matrix'] == []
    login(browser)
    first = browser.get('/v1/control').json()
    second = browser.get('/v1/control').json()
    assert len(first['reports']) == len(second['reports']) == 1
    assert first['reports'][0]['state'] == 'CONFIRMED'
