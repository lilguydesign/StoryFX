"""Synthetic media-mode dispatch, capability revocation and no historical auto-send."""
import pytest
from datetime import datetime, timezone
from test_private_auth import private
from test_control_android import setup, start
from test_control_center import add, HEADERS
from storyfx_server.control_android import executors
from storyfx_server.control_media_modes import supported_media, media_count


def value(engine='intro+multi', count=11):
    return dict(device='Validation technique', platform='WhatsApp', engine=engine, count=count,
                album='Validation technique introduction', album2='Validation technique')


def configure(browser, engine):
    add(browser, 'albums', name='Validation technique introduction')
    snapshot = browser.get('/v1/control').json()
    row = snapshot['collections']['matrix'][0]
    payload = {k: v for k, v in row.items() if k != 'id'}
    payload.update(value(engine, 3))
    result = browser.put('/v1/control/settings/matrix/' + row['id'], headers=HEADERS,
                         json={'revision': snapshot['revision'], 'value': payload})
    assert result.status_code == 200


@pytest.mark.parametrize('engine,total', [('intro', 1), ('multi', 11), ('intro+multi', 12)])
def test_modes_keep_multi_count_and_intro_is_additional(engine, total):
    assert supported_media(value(engine))
    assert media_count(value(engine)) == total
    assert not supported_media({**value(engine), 'platform': 'Facebook'})
    assert not supported_media({**value(engine), 'page_name': 'Validation technique autre'})
    assert not supported_media(value(engine, 0))
    assert not supported_media(value(engine, 31))
    assert not supported_media(value('intro+multi', 30))


def test_legacy_agent_and_windows_never_receive_new_modes():
    old = dict(connected=True, profiles=['Validation technique'], executor='android_whatsapp_images_v1')
    modern = {**old, 'media_modes_ready': True}
    windows = {**old, 'executor': 'windows_bridge'}
    assert executors({'nodes': [old, windows]}, value()) == []
    assert executors({'nodes': [old, modern, windows]}, value()) == [modern]
    assert executors({'nodes': [old]}, value('multi')) == [old]
    assert executors({'nodes': [old]}, {**value('multi'), 'album2': 'Video'}) == []
    assert executors({'nodes': [modern]}, {**value('multi'), 'album2': 'Video'}) == [modern]


@pytest.mark.parametrize('engine', ['intro', 'intro+multi'])
def test_native_modes_one_attempt_and_video_permission_revocation(private, engine):
    app, browser, _, now, auth, contact, _ = setup(private)
    configure(browser, engine)
    now[0] = datetime(2023, 11, 15, 13, tzinfo=timezone.utc).timestamp()
    modern = {**contact, 'app_version': '0.4.13', 'media_modes_ready': True}
    assert browser.post('/v1/control/android/heartbeat', headers=auth, json=modern).status_code == 200
    assert start(browser).status_code == 200
    job = browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job']
    assert job['payload']['engine'] == engine
    path = '/v1/control/android/jobs/' + job['id']
    assert browser.post(path + '/ready', headers=auth, json={}).status_code == 200
    browser.post('/v1/control/android/heartbeat', headers=auth, json={**modern, 'media_modes_ready': False})
    assert browser.post(path + '/ready', headers=auth, json={}).status_code == 409
    result = {'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain'}
    assert browser.post(path + '/complete', headers=auth, json=result).status_code == 200
    app.state.control_scheduler.tick()
    assert len(browser.get('/v1/control').json()['reports']) == 2
    assert sum(row['state'] == 'NEEDS_REVIEW' for row in browser.get('/v1/control').json()['reports']) == 1


def test_rollout_does_not_backfill_previously_unsupported_occurrences(private):
    app, browser, _, now, auth, contact, _ = setup(private)
    configure(browser, 'intro+multi')
    # These two occurrences precede the durable v2 rollout timestamp.
    app.state.control_scheduler.broker.android.media_enabled_from = now[0] + 1
    browser.post('/v1/control/android/heartbeat', headers=auth,
                 json={**contact, 'app_version': '0.4.13', 'media_modes_ready': True})
    assert start(browser).status_code == 200
    assert browser.get('/v1/control').json()['reports'] == []
    assert browser.post('/v1/control/android/claim', headers=auth, json={}).json()['job'] is None
