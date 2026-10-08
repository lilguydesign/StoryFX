"""Explicit owner permissions remain separate from native publishing capability."""
from uuid import uuid4
from test_private_auth import private, login, enroll
from test_control_center import HEADERS, add
from android_profile_fixtures import ROOT, fixture, associate, remove, internals


def test_additive_permissions_keep_primary_and_all_execution_state(private):
    app, browser, _, _, auth, _, body = fixture(private)
    before = internals(app)
    first = associate(browser, body)
    assert first.status_code == 200, first.text
    profiles = browser.get('/v1/control').json()['collections']['profiles']
    other = next(row for row in profiles if row['name'] == 'Validation technique 3')
    assert associate(browser, {**body, 'client_key': str(uuid4()), 'profile_id': other['id']}).status_code == 200
    assert internals(app) == before
    data = browser.post('/v1/control/android/settings', headers=auth, json={}).json()
    assert data['binding'] == {'profile': 'Validation technique', 'enabled': 1, 'reason': ''}
    assert data['executor'] == 'android_whatsapp_images_v1'
    assert all(set(row) == {'name', 'enabled'} for row in data['profiles'])
    assert {(row['profile'], row['platform'], row['primary']) for row in data['authorized_profiles']} == {
        ('Validation technique', 'WhatsApp', True), ('Validation technique 2', 'Facebook', False),
        ('Validation technique 3', 'Facebook', False)}
    assert data['authorized_profiles'][0]['primary'] is True
    assert data['authorized_profiles'][0]['ready'] is True
    assert all(not row['ready'] for row in data['authorized_profiles'][1:])
    assert data['capabilities']['facebook'] == {'ready': False, 'reason': 'ADAPTER_NOT_VALIDATED',
        'contract_version': 1, 'manual_trial_ready': False, 'auto_ready': False,
        'identity_contract': None, 'media_contract': None, 'proof_contract': None}
    assert 'synthetic-shared-hardware' not in str(data)
    listing = browser.get(ROOT).json()
    assert len(listing['bindings']) == 2 and listing['revision'] == body['revision']


def test_idempotent_permission_retry_cannot_resurrect_removed_binding(private):
    _, browser, _, _, _, _, body = fixture(private)
    binding = associate(browser, body).json()
    assert associate(browser, body).json() == binding
    assert associate(browser, {**body, 'platform': 'Facebook', 'profile_id': str(uuid4())}).json()['error'] == 'IDEMPOTENCY_KEY_CONFLICT'
    removed = remove(browser, binding, body['revision']).json()
    assert removed['active'] is False
    add(browser, 'albums', name='Validation technique 2')
    assert remove(browser, binding, body['revision']).json() == removed
    assert associate(browser, body).json() == removed
    assert len(browser.get(ROOT).json()['bindings']) == 1
    replacement = {**body, 'client_key': str(uuid4()), 'revision': browser.get(ROOT).json()['revision']}
    assert associate(browser, replacement).json()['active'] is True


def test_owner_origin_role_and_canonical_profile_checks(private):
    _, browser, provider, _, _, _, body = fixture(private)
    assert browser.post(ROOT, json=body).json()['error'] == 'ORIGIN_REFUSED'
    assert associate(browser, {**body, 'platform': 'WhatsApp'}).status_code == 422
    assert associate(browser, {**body, 'profile_id': str(uuid4())}).json()['error'] == 'PROFILE_NOT_FOUND'
    assert associate(browser, {**body, 'revision': body['revision'] - 1}).json()['error'] == 'CONFIGURATION_CHANGED'
    binding = associate(browser, body).json()
    login(browser, 'owner-b')
    assert browser.get(ROOT).json()['bindings'] == []
    assert associate(browser, {**body, 'revision': 0}).json()['error'] == 'DEVICE_NOT_FOUND_OR_REVOKED'
    assert remove(browser, binding, 0).status_code == 404
    login(browser)
    provider.denied.add('owner-a')
    assert browser.get(ROOT).status_code == 403
    assert remove(browser, binding, body['revision']).status_code == 403


def test_permission_requires_existing_primary_and_unique_profile(private):
    _, browser, _, _, auth, _, body = fixture(private)
    other = browser.post('/v1/auth/agent/exchange', json=enroll(browser)).json()
    other_body = {**body, 'client_key': str(uuid4()), 'device_id': other['device_id']}
    assert associate(browser, other_body).json()['error'] == 'ANDROID_PRIMARY_BINDING_REQUIRED'
    other_auth = {'Authorization': 'Bearer ' + other['token']}
    assert browser.post('/v1/control/android/bind', headers=other_auth,
                        json={'profile': 'Validation technique 4', 'enabled': True}).status_code == 200
    binding = associate(browser, body).json()
    assert associate(browser, other_body).json()['error'] == 'ANDROID_PROFILE_ALREADY_BOUND'
    assert browser.post('/v1/control/android/bind', headers=auth,
                        json={'profile': 'Validation technique 2', 'enabled': True}).json()['error'] == 'ANDROID_PROFILE_ALREADY_BOUND'
    assert browser.post('/v1/control/android/bind', headers=auth,
                        json={'profile': 'Validation technique 3', 'enabled': True}).json()['error'] == 'ANDROID_SECONDARY_BINDINGS_PRESENT'
    primary = next(p for p in browser.get('/v1/control').json()['collections']['profiles'] if p['name'] == 'Validation technique')
    assert associate(browser, {**body, 'client_key': str(uuid4()), 'profile_id': primary['id']}).json()['error'] == 'ANDROID_PROFILE_ALREADY_BOUND'
    assert remove(browser, binding, body['revision']).status_code == 200
    assert browser.post('/v1/control/android/bind', headers=auth,
                        json={'profile': 'Validation technique 3', 'enabled': True}).status_code == 200


def test_deleted_profile_cannot_transfer_authorization_by_reusing_name(private):
    _, browser, _, _, auth, _, body = fixture(private)
    binding = associate(browser, body).json()
    path = '/v1/control/settings/profiles/' + body['profile_id']
    assert browser.post(path + '/remove', headers=HEADERS, json={'revision': body['revision']}).status_code == 200
    add(browser, 'profiles', name='Validation technique 2')
    data = browser.post('/v1/control/android/settings', headers=auth, json={}).json()
    assert len(data['authorized_profiles']) == 1
    listing = browser.get(ROOT).json()['bindings'][0]
    assert listing['id'] == binding['id'] and listing['reason'] == 'PROFILE_NOT_FOUND'
    assert listing['profile'] is None and listing['ready'] is False


def test_facebook_and_secondary_whatsapp_remain_unavailable(private):
    _, browser, _, _, auth, _, body = fixture(private)
    associate(browser, body)
    add(browser, 'matrix', name='Validation technique FB', device='Validation technique 2', platform='Facebook',
        system='Validation technique', engine='multi', album2='Validation technique', count=3, page='Validation technique')
    add(browser, 'matrix', name='Validation technique WA', device='Validation technique 2', platform='WhatsApp',
        system='Validation technique', engine='multi', album2='Validation technique', count=3)
    snapshot = browser.get('/v1/control').json()
    for value in snapshot['schedule']:
        if value['device'] == 'Validation technique 2':
            result = browser.post('/v1/control/launch', headers=HEADERS,
                                  json={'revision': snapshot['revision'], 'occurrence_id': value['id']})
            assert result.status_code == 409
    fb = next(row for row in snapshot['collections']['matrix'] if row['platform'] == 'Facebook')
    response = browser.post('/v1/control/recipes', headers=HEADERS,
                            json={'client_key': str(uuid4()), 'executor': 'android', 'revision': snapshot['revision'], 'row_ids': [fb['id']]})
    assert response.json()['error'] == 'ADAPTER_NOT_VALIDATED'
    assert browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job'] is None
    assert browser.get('/health').json()['native_platforms_supported'] == ['WhatsApp']
    assert browser.get('/v1/control').json()['reports'] == []


def test_disabled_revoked_and_foreign_profile_permissions_are_refused(private):
    _, browser, _, _, _, _, body = fixture(private)
    path = '/v1/control/settings/profiles/' + body['profile_id']
    result = browser.put(path, headers=HEADERS, json={'revision': body['revision'], 'value': {'enabled': False}})
    assert result.status_code == 200
    body['revision'] = result.json()['revision']
    assert associate(browser, body).json()['error'] == 'PROFILE_NOT_FOUND'
    login(browser, 'owner-b')
    foreign = add(browser, 'profiles', name='Validation technique')
    foreign_id = foreign['collections']['profiles'][0]['id']
    login(browser)
    assert associate(browser, {**body, 'profile_id': foreign_id}).json()['error'] == 'PROFILE_NOT_FOUND'
    assert browser.post('/v1/devices/' + body['device_id'] + '/revoke', headers=HEADERS, json={}).status_code == 200
    assert associate(browser, body).json()['error'] == 'DEVICE_NOT_FOUND_OR_REVOKED'


def test_agent_credential_alone_cannot_grant_profile_permissions(private):
    _, browser, _, _, auth, _, body = fixture(private)
    browser.cookies.clear()
    assert browser.get(ROOT, headers=auth).status_code == 401
    assert browser.post(ROOT, headers={**auth, **HEADERS}, json=body).status_code == 401


def test_concurrent_permissions_have_one_winner_and_same_key_one_receipt(private):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from storyfx_server.control_android_profile_routes import ProfileAssociation
    from storyfx_server.store import DomainError
    app, browser, _, _, _, _, body = fixture(private)
    bindings = app.state.control_scheduler.broker.android.profile_bindings
    barrier = Barrier(2)

    def apply(value):
        barrier.wait(timeout=5)
        try:
            return bindings.add({'id': 'owner-a'}, ProfileAssociation(**value))
        except DomainError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, [body, {**body, 'client_key': str(uuid4())}]))
    assert sum(isinstance(value, dict) for value in results) == 1
    assert 'ANDROID_PROFILE_ALREADY_BOUND' in results
    winner = next(value for value in results if isinstance(value, dict))
    same = {**body, 'client_key': winner['client_key']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, [same, same]))
    assert results == [winner, winner]
    assert len(browser.get(ROOT).json()['bindings']) == 1


def test_limit_preserves_one_primary_and_99_secondaries_without_blocking_whatsapp(private):
    import json
    app, browser, _, now, auth, _, body = fixture(private)
    # Seed a large synthetic catalogue, then exercise both boundary mutations through the API.
    with app.state.store.transaction() as db:
        link = db.execute('SELECT * FROM control_android_links WHERE device_id=?', (body['device_id'],)).fetchone()
        for index in range(98):
            profile_id = str(uuid4())
            name = 'Validation technique supplémentaire ' + str(index)
            db.execute('INSERT INTO control_items VALUES (?,?,?,?,?)',
                       (profile_id, 'owner-a', 'profiles', json.dumps({'name': name, 'enabled': True}), name))
            db.execute('INSERT INTO control_android_profiles VALUES (?,?,?,?,?,?,?,?,?,NULL)',
                       (str(uuid4()), 'owner-a', body['device_id'], link['node_id'], profile_id,
                        'Facebook', str(uuid4()), 'synthetic-request', now[0]))
    binding = associate(browser, body)
    assert binding.status_code == 200
    before = internals(app)
    snapshot = browser.get('/v1/control').json()
    other = next(row for row in snapshot['collections']['profiles'] if row['name'] == 'Validation technique 3')
    denied = associate(browser, {**body, 'client_key': str(uuid4()), 'profile_id': other['id']})
    assert denied.status_code == 409 and denied.json()['error'] == 'ANDROID_PROFILE_LIMIT_REACHED'
    assert internals(app) == before
    settings = browser.post('/v1/control/android/settings', headers=auth, json={}).json()
    assert len(settings['authorized_profiles']) == 100
    assert sum(row['primary'] for row in settings['authorized_profiles']) == 1
    assert sum(row['ready'] for row in settings['authorized_profiles']) == 1
    assert len(browser.get(ROOT).json()['bindings']) == 99
    launch = browser.post('/v1/control/launch', headers=HEADERS,
                          json={'revision': snapshot['revision'], 'occurrence_id': snapshot['schedule'][0]['id']})
    assert launch.status_code == 200
    # An existing receipt wins over both the capacity bound and newly queued work.
    assert associate(browser, body).json() == binding.json()
    job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    assert job['payload']['platform'] == 'WhatsApp' and job['payload']['device'] == 'Validation technique'


def test_owner_listing_maps_only_canonical_devices_and_keeps_revoked_primary_reserved(private):
    _, browser, _, _, _, _, body = fixture(private)
    unbound = browser.post('/v1/auth/agent/exchange', json=enroll(browser)).json()['device_id']
    listing = browser.get(ROOT).json()
    assert len(listing['devices']) == 1
    device = listing['devices'][0]
    assert set(device) == {'device_id', 'name', 'primary_profile_id', 'primary_profile', 'revoked'}
    assert device['device_id'] == body['device_id'] and device['device_id'] != unbound
    assert device['primary_profile'] == 'Validation technique' and device['revoked'] is False
    assert listing['primary_profile_ids'] == [device['primary_profile_id']]
    assert 'synthetic-shared-hardware' not in str(listing)
    login(browser, 'owner-b')
    other = browser.get(ROOT).json()
    assert other['devices'] == [] and other['primary_profile_ids'] == []
    login(browser)
    browser.post('/v1/devices/' + body['device_id'] + '/revoke', headers=HEADERS, json={})
    revoked = browser.get(ROOT).json()
    assert revoked['devices'] == [] and revoked['primary_profile_ids'] == [device['primary_profile_id']]
