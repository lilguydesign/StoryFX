"""Editable transport metadata remains tenant-bound and never executes commands."""
from test_control_center import settings, add, executor, HEADERS
from test_private_auth import private, login


def test_full_profile_roundtrip_and_partial_edit_preserves_transport(private):
    _,browser,_,_=private
    login(browser); settings(browser)
    snapshot=browser.get('/v1/control').json();profile=snapshot['collections']['profiles'][0]
    value={'name':profile['name'],'device_id':'192.0.2.1:5555','adb_serial':'SYNTHETIC001',
           'tcpip_ip':'192.0.2.1','tcpip_port':5555,'platform_version':'16','offset_minutes':42,
           'appium_overrides':{'adbExecTimeout':60000},
           'gallery':{'appPackage':'com.sec.android.gallery3d','appActivity':'.app.GalleryActivity'}}
    assert browser.put('/v1/control/settings/profiles/'+profile['id'],headers=HEADERS,json={'revision':snapshot['revision'],'value':value}).status_code==200
    current=browser.get('/v1/control').json()
    assert current['collections']['profiles'][0]['adb_serial']=='SYNTHETIC001'
    updated=browser.put('/v1/control/settings/profiles/'+profile['id'],headers=HEADERS,json={'revision':current['revision'],'value':{'name':profile['name'],'label':'Validation technique'}})
    assert updated.status_code==200 and updated.json()['collections']['profiles'][0]['tcpip_port']==5555
    auth=executor(browser)
    assert browser.post('/v1/control/windows/settings',headers=auth,json={}).json()['profiles'][0]['adb_serial']=='SYNTHETIC001'


def test_profile_refuses_commands_unsafe_capabilities_and_invalid_addresses(private):
    _,browser,_,_=private
    login(browser)
    for bad in ({'appium_overrides':{'fullReset':True}}, {'appium_overrides':{'autoGrantPermissions':True}},
                {'appium_overrides':{'executeDriverScript':'forbidden'}}, {'device_id':'shell;command'},
                {'tcpip_ip':'https://example.invalid'}, {'tcpip_port':70000}, {'gallery':{'appPackage':'bad;command'}}):
        snapshot=browser.get('/v1/control').json()
        response=browser.post('/v1/control/settings/profiles',headers=HEADERS,json={'revision':snapshot['revision'],'value':{'name':'Validation technique',**bad}})
        assert response.status_code==422


def test_propagation_is_atomic_only_for_previously_shared_phone(private):
    _,browser,_,_=private
    login(browser)
    for name,serial in [('Validation technique','SYNTHETIC001'),('Validation technique 2','SYNTHETIC001'),('Validation technique 3','SYNTHETIC002')]:
        add(browser,'profiles',name=name,adb_serial=serial,device_id='192.0.2.1:5555' if serial=='SYNTHETIC001' else '192.0.2.2:5555')
    snapshot=browser.get('/v1/control').json();profile=snapshot['collections']['profiles'][0]
    response=browser.put('/v1/control/settings/profiles/'+profile['id'],headers=HEADERS,json={'revision':snapshot['revision'],'value':{'name':profile['name'],'device_id':'192.0.2.3:5556','tcpip_ip':'192.0.2.3','tcpip_port':5556,'adb_serial':'SYNTHETIC003'},'propagate_device':True,'propagate_serial':True})
    assert response.status_code==200
    rows=response.json()['collections']['profiles']
    assert [row['adb_serial'] for row in rows]==['SYNTHETIC003','SYNTHETIC003','SYNTHETIC002']
