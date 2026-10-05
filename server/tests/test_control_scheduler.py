"""Synthetic catch-up, durable scheduler, stop and private terminal contracts."""
from datetime import datetime, timezone
from test_control_center import settings, executor, add, HEADERS
from test_private_auth import private, login


def setup(private):
    app,browser,provider,now = private
    login(browser); settings(browser)
    now[0]=datetime(2023,11,14,13,tzinfo=timezone.utc).timestamp()
    auth=executor(browser)
    browser.post('/v1/control/windows/heartbeat',headers=auth,json={'profiles':['Validation technique']})
    snapshot=browser.get('/v1/control').json()
    body={'revision':snapshot['revision'],'profiles':['Validation technique'],'platforms':['WhatsApp'],'start_time':'05:00'}
    return app,browser,provider,now,auth,body


def test_catchup_excludes_prior_request_and_is_idempotent(private):
    _,browser,_,_,auth,body=setup(private)
    preview=browser.post('/v1/control/catchup/preview',headers=HEADERS,json=body).json()
    assert preview['eligible_count']==2
    first=browser.post('/v1/control/catchup/launch',headers=HEADERS,json=body).json()
    assert first['queued']==2
    assert browser.post('/v1/control/catchup/launch',headers=HEADERS,json=body).json()['queued']==0
    job=browser.post('/v1/control/windows/claim',headers=auth,json={}).json()['job']
    browser.post('/v1/control/windows/jobs/'+job['id']+'/complete',headers=auth,json={'state':'CONFIRMED','evidence':'own_status_verified'})
    assert browser.post('/v1/control/catchup/preview',headers=HEADERS,json=body).json()['eligible_count']==0


def test_stop_cancels_queue_and_denies_final_action_without_replay(private):
    _,browser,_,_,auth,body=setup(private)
    browser.post('/v1/control/catchup/launch',headers=HEADERS,json=body)
    job=browser.post('/v1/control/windows/claim',headers=auth,json={}).json()['job']
    stopped=browser.post('/v1/control/stop',headers=HEADERS,json={}).json()
    assert stopped['queued_cancelled']==1 and stopped['running_stop_requested']==1
    assert browser.post('/v1/control/windows/jobs/'+job['id']+'/ready',headers=auth,json={}).status_code==409
    assert browser.post('/v1/control/windows/claim',headers=auth,json={}).json()['job'] is None
    # A provider action already in flight may still confirm truthfully after stop.
    assert browser.post('/v1/control/windows/jobs/'+job['id']+'/complete',headers=auth,json={'state':'CONFIRMED','evidence':'own_status_verified'}).status_code==200
    assert browser.post('/v1/control/catchup/launch',headers=HEADERS,json=body).json()['queued']==0


def test_configuration_change_denies_final_provider_action(private):
    _,browser,_,_,auth,body=setup(private)
    browser.post('/v1/control/catchup/launch',headers=HEADERS,json=body)
    job=browser.post('/v1/control/windows/claim',headers=auth,json={}).json()['job']
    add(browser,'albums',name='Validation technique nouveau réglage')
    assert browser.post('/v1/control/windows/jobs/'+job['id']+'/ready',headers=auth,json={}).status_code==409


def test_scheduler_manual_returns_auto_and_stop_is_persistent(private):
    app,browser,_,_,_,body=setup(private)
    started=browser.post('/v1/control/scheduler/start',headers=HEADERS,json={**body,'mode':'manual'})
    assert started.status_code==200 and started.json()['enabled'] and started.json()['mode']=='auto'
    assert len(browser.get('/v1/control').json()['reports'])==2
    app.state.control_scheduler.tick()
    assert len(browser.get('/v1/control').json()['reports'])==2
    browser.post('/v1/control/scheduler/stop',headers=HEADERS,json={})
    app.state.control_scheduler.tick()
    assert not browser.get('/v1/control').json()['scheduler']['enabled']
    assert {row['state'] for row in browser.get('/v1/control').json()['reports']}=={'CANCELLED'}


def test_auto_has_no_past_catchup_and_revision_change_pauses(private):
    app,browser,_,now,auth,body=setup(private)
    now[0]=datetime(2023,11,14,5,tzinfo=timezone.utc).timestamp()
    browser.post('/v1/control/windows/heartbeat',headers=auth,json={'profiles':['Validation technique']})
    response=browser.post('/v1/control/scheduler/start',headers=HEADERS,json={**body,'mode':'auto'})
    assert response.status_code==200
    assert browser.get('/v1/control').json()['reports']==[]
    add(browser,'albums',name='Validation technique 2')
    app.state.control_scheduler.tick()
    assert not browser.get('/v1/control').json()['scheduler']['enabled']
    assert browser.get('/v1/control').json()['scheduler']['wait_reason']=='CONFIGURATION_CHANGED'


def test_revocation_pauses_scheduler_and_terminal_clear_retains_audit(private):
    app,browser,provider,_,_,body=setup(private)
    browser.post('/v1/control/scheduler/start',headers=HEADERS,json={**body,'mode':'manual'})
    assert browser.get('/v1/control').json()['terminal']
    browser.post('/v1/control/terminal/clear',headers=HEADERS,json={})
    assert browser.get('/v1/control').json()['terminal']==[]
    with app.state.store.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM control_events').fetchone()[0]>0
    provider.denied.add('owner-a'); app.state.control_scheduler.tick()
    with app.state.store.transaction() as db:
        assert db.execute('SELECT enabled FROM control_schedulers').fetchone()[0]==0


def test_catchup_bounds_origin_tenant_and_unvalidated_adapter(private):
    _,browser,_,_,_,body=setup(private)
    assert browser.post('/v1/control/catchup/launch',json=body).status_code==403
    assert browser.post('/v1/control/catchup/preview',headers=HEADERS,json={**body,'start_time':'23:00'}).status_code==422
    assert browser.post('/v1/control/catchup/preview',headers=HEADERS,json={**body,'end_time':'23:00'}).status_code==422
    assert browser.post('/v1/control/catchup/preview',headers=HEADERS,json={**body,'profiles':['unknown']}).status_code==422
    login(browser,'owner-b')
    assert browser.get('/v1/control').json()['terminal']==[]
    assert not browser.get('/v1/control').json()['scheduler']['enabled']
    assert browser.post('/v1/control/catchup/preview',headers=HEADERS,json=body).status_code in (409,422)
