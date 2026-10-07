"""Install only the bounded StoryFX evidence timer; never alter its publication scheduler."""
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time


def install(release, config):
    assert socket.gethostname() == 'formafx-prod-db-02' and os.geteuid() == 0
    release = Path(release).resolve()
    assert release.parent == Path('/opt/formafx/storyfx/releases')
    folder = Path('/opt/formafx/storyfx/state')
    assert config['end_unix'] - config['start_unix'] == 7 * 86400
    assert config['start_unix'] <= time.time() < config['end_unix']
    assert all(isinstance(config[key], list) and 0 < len(config[key]) <= 10 for key in
               ('device_profiles', 'schedule_profiles', 'whatsapp_forbidden_profiles'))
    with sqlite3.connect('file:' + str(folder / 'storyfx.db') + '?mode=ro', uri=True) as db:
        assert db.execute('SELECT 1 FROM control_owners WHERE owner_id=?', (config['owner_id'],)).fetchone()
        known = {r[0] for r in db.execute("SELECT json_name FROM control_items WHERE owner_id=? AND collection='profiles'", (config['owner_id'],))}
        assert all(set(config[key]) <= known for key in ('device_profiles', 'schedule_profiles', 'whatsapp_forbidden_profiles'))
    destination = folder / 'observation-config.json'
    if destination.exists():
        assert json.loads(destination.read_text()) == config, 'EXISTING_WINDOW_PRESERVED'
    else:
        with destination.open('x') as output:
            os.chmod(destination, 0o600)
            identity = (folder / 'storyfx.db').stat()
            os.chown(destination, identity.st_uid, identity.st_gid)
            json.dump(config, output)
    for name in ('storyfx-observation.service', 'storyfx-observation.timer'):
        source, target = release / 'deploy' / name, Path('/etc/systemd/system') / name
        if target.exists() and target.read_bytes() != source.read_bytes():
            backup = folder / (name + '.' + str(int(time.time())) + '.backup')
            shutil.copy2(target, backup)
            os.chmod(backup, 0o600)
        shutil.copyfile(source, target)
        os.chmod(target, 0o644)
    subprocess.run(['systemctl','daemon-reload'], check=True)
    subprocess.run(['systemctl','start','storyfx-observation.service'], check=True)
    subprocess.run(['systemctl','enable','--now','storyfx-observation.timer'], check=True, capture_output=True)
    assert subprocess.check_output(['systemctl','is-active','storyfx-observation.timer']).strip() == b'active'
    state = json.loads((folder / 'observation-state.json').read_text())
    assert state['read_only'] and state['observations']
    return {'timer_active':True,'first_server_collection_verified':True,'interval_minutes':30,
            'end_unix':config['end_unix'],'usb_required':False,'scheduler_modified':False,
            'real_send_triggered':False,'total_autonomy_verified':False}


if __name__ == '__main__':
    print(json.dumps(install(sys.argv[1], json.load(sys.stdin))))
