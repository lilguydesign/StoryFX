"""A disabled channel must disappear without disabling a shared physical phone."""
from test_private_auth import private, login
from test_control_center import settings, add, executor, HEADERS


def test_disabled_matrix_preserves_profile_other_channels_and_occurrence(private):
    _, browser, _, _ = private
    login(browser); settings(browser)
    add(browser, 'matrix', name='Validation technique Facebook', device='Validation technique',
        platform='Facebook', system='Validation technique', engine='multi', album2='Validation technique',
        count=3, page_name='Validation technique')
    before = browser.get('/v1/control').json()
    wa = next(r for r in before['collections']['matrix'] if r['platform'] == 'WhatsApp')
    original = next(s['id'] for s in before['schedule'] if s['platform'] == 'WhatsApp')
    auth = executor(browser)
    browser.post('/v1/control/windows/heartbeat', headers=auth, json={'profiles': ['Validation technique']})
    response = browser.put('/v1/control/settings/matrix/' + wa['id'], headers=HEADERS,
        json={'revision': before['revision'], 'value': {k:v for k,v in {**wa,'enabled':False}.items() if k != 'id'}})
    assert response.status_code == 200
    after = browser.get('/v1/control').json()
    assert after['collections']['profiles'][0]['enabled']
    assert {r['platform'] for r in after['schedule']} == {'Facebook'}
    assert not after['reports']
    refused = browser.post('/v1/control/launch', headers=HEADERS,
        json={'revision': after['revision'], 'occurrence_id': original})
    assert refused.status_code == 404
    assert len(after['collections']['matrix']) == 2


def test_legacy_rows_default_enabled_and_disabled_payload_refused():
    from storyfx_server.control_models import Matrix
    from storyfx_server.control_publications import supported
    value = dict(name='Validation technique', device='Validation technique', platform='WhatsApp',
                 system='Validation technique', engine='multi', album='Validation technique', count=3)
    assert Matrix.model_validate(value).enabled
    assert supported(value)
    assert not supported({**value, 'enabled': False})
    assert not supported({**value, 'album': ''})
