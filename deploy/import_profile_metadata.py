"""Add missing legacy profile columns once, bound to the authenticated seed owner."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from storyfx_server.auth_client import AuthClient
from storyfx_server.auth_sessions import AuthSessions
from storyfx_server.control_catalog import Catalog
from storyfx_server.store import Store

KEYS=('device_id','adb_serial','tcpip_ip','tcpip_port','platform_version','appium_overrides','gallery')


def import_metadata(state,source):
    assert Path('/.dockerenv').is_file(), 'TARGET_CONTAINER_REQUIRED'
    state=Path(state).resolve(strict=True)
    assert str(state)=='/data'
    source=Path(source).resolve(strict=True)
    assert source.parent==state and source.name=='profile-metadata.json'
    data=json.loads(source.read_text())
    seed=json.loads((state/'control-seed.json').read_text())
    assert data['owner_email'].casefold()==seed['owner_email'].casefold()
    store=Store(state/'storyfx.db')
    sessions=AuthSessions(store,AuthClient.discover(),(state/'session.key').read_bytes())
    with store.transaction() as db:
        candidates=[dict(row) for row in db.execute('SELECT DISTINCT owner_id,auth_session_hash FROM devices WHERE revoked=0 AND auth_session_hash IS NOT NULL')]
    users=[]
    for row in candidates:
        try:
            user=sessions.require_hash(row['auth_session_hash'])
            if user['id']==row['owner_id'] and user['email'].casefold()==data['owner_email'].casefold():
                users.append(user)
        except Exception:
            continue
    assert len({user['id'] for user in users})==1, 'AUTHENTICATED_OWNER_NOT_UNIQUE'
    user=users[0]; changed=0
    with store.transaction() as db:
        rows=db.execute("SELECT id,value FROM control_items WHERE owner_id=? AND collection='profiles'",(user['id'],)).fetchall()
        for row in rows:
            current=json.loads(row['value']); legacy=data['profiles'].get(current['name'])
            if not legacy:
                continue
            missing={key:legacy[key] for key in KEYS if key in legacy and key not in current}
            if not missing:
                continue
            clean=Catalog.validate('profiles',{**current,**missing})
            db.execute('UPDATE control_items SET value=? WHERE id=?',(json.dumps(clean),row['id']))
            changed+=1
        if changed:
            db.execute('UPDATE control_owners SET revision=revision+1 WHERE owner_id=?',(user['id'],))
            db.execute('UPDATE control_schedulers SET enabled=0,wait_reason=? WHERE owner_id=?',('CONFIGURATION_CHANGED',user['id']))
    return {'profile_metadata_imported':True,'profiles_enriched':changed,
            'existing_fields_overwritten':False,'private_identifiers_logged':False,
            'adb_connected_by_migration':False,'real_send_triggered':False}


if __name__=='__main__':
    try:
        print(json.dumps(import_metadata(*sys.argv[1:])))
    except Exception as error:
        print(json.dumps({'profile_metadata_imported':False,'error_kind':type(error).__name__,
                          'private_identifiers_logged':False,'real_send_triggered':False}))
        raise SystemExit(1)
