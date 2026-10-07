"""Synthetic Vault boundary: active owner, bound profile, no publication side effects."""
from test_control_android import setup
from test_private_auth import private


def request(browser, auth, operation, **changes):
    body = {'profile': 'Validation technique', 'consent': True, **changes}
    return browser.post('/v1/control/android/pin-backup/' + operation, headers=auth, json=body)


def vault(provider):
    calls = []
    def call(method, path, body, access=None):
        assert method == 'POST' and path == '/rest/v1/rpc/storyfx_pin_backup_v1'
        calls.append((dict(body), access))
        return {'available': True, 'pin': '1234', 'updated_at': 'synthetic'}
    provider.call = call
    return calls


def test_bound_owner_roundtrip_and_save_never_echoes_pin(private):
    app, browser, provider, _, auth, _, _ = setup(private)
    calls = vault(provider)
    saved = request(browser, auth, 'save', pin='1234')
    assert saved.status_code == 200 and 'pin' not in saved.json()
    assert '1234' not in saved.text and 'access-' not in saved.text
    assert calls[-1][0]['p_pin'] == '1234'
    restored = request(browser, auth, 'restore')
    assert restored.status_code == 200 and restored.json()['pin'] == '1234'
    assert restored.headers['cache-control'] == 'no-store'
    with app.state.store.transaction() as db:
        assert db.execute('SELECT count(*) FROM control_jobs').fetchone()[0] == 0


def test_other_profile_consent_bad_pin_and_owner_revocation(private):
    _, browser, provider, _, auth, _, _ = setup(private)
    calls = vault(provider)
    assert request(browser, auth, 'restore', profile='Other').status_code == 403
    assert request(browser, auth, 'save', pin='invalid').status_code == 422
    assert request(browser, auth, 'save', pin='1234', consent=False).status_code == 422
    assert not calls
    provider.denied.add('owner-a')
    assert request(browser, auth, 'restore').status_code == 403
    assert not calls


def test_disabled_channel_backup_does_not_enable_publication(private):
    app, browser, provider, _, auth, _, device = setup(private)
    vault(provider)
    with app.state.store.transaction() as db:
        db.execute('UPDATE control_android_links SET enabled=0,ready=0 WHERE device_id=?', (device,))
    assert request(browser, auth, 'save', pin='1234').status_code == 200
    with app.state.store.transaction() as db:
        assert db.execute('SELECT enabled FROM control_android_links WHERE device_id=?', (device,)).fetchone()[0] == 0
        db.execute('UPDATE devices SET revoked=1 WHERE id=?', (device,))
    assert request(browser, auth, 'restore').status_code == 401


def test_wrong_binding_and_malformed_vault_response(private):
    app, browser, provider, _, auth, _, _ = setup(private)
    vault(provider)
    provider.call = lambda *args: {'available': True, 'pin': 'invalid'}
    result = request(browser, auth, 'restore')
    assert result.status_code == 503 and 'invalid' not in result.text
    with app.state.store.transaction() as db:
        db.execute('UPDATE control_android_links SET profile=?', ('Other',))
    assert request(browser, auth, 'status').status_code == 403
