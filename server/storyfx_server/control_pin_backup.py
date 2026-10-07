"""Bound installation + live owner gate; secrets exist only in Vault and memory."""
import re
from typing import Literal
from fastapi import Depends
from pydantic import Field, SecretStr
from .control_models import Strict
from .store import DomainError


class BackupRequest(Strict):
    profile: str = Field(min_length=1, max_length=100)
    consent: Literal[True]


class SaveBackup(BackupRequest):
    pin: SecretStr


class PinBackups:
    def __init__(self, broker):
        self.broker = broker

    def call(self, identity, body, operation):
        native = self.broker.android
        user = native.principal(identity)
        with native.store.transaction() as db:
            native.store.authenticate_in_transaction(db, identity)
            link = db.execute('SELECT a.profile,n.revoked FROM control_android_links a '
                              'JOIN control_nodes n ON n.id=a.node_id '
                              'WHERE a.device_id=? AND a.owner_id=?',
                              (identity.id, user['id'])).fetchone()
        if not link or link['revoked'] or link['profile'] != body.profile:
            raise DomainError('BACKUP_PROFILE_REFUSED', 403)
        profiles = self.broker.catalog.read(user)['collections']['profiles']
        if not any(row['name'] == body.profile and row.get('enabled', True) for row in profiles):
            raise DomainError('BACKUP_PROFILE_REFUSED', 403)
        # Disabled publication channels may back up credentials without enabling gestures.
        args = {'p_operation': operation, 'p_profile': body.profile}
        if operation == 'save':
            pin = body.pin.get_secret_value()
            if not re.fullmatch(r'[0-9]{4,16}', pin):
                raise DomainError('BACKUP_PIN_INVALID', 422)
            args['p_pin'] = pin
        try:
            value = self.broker.sessions.client.call('POST', '/rest/v1/rpc/storyfx_pin_backup_v1',
                                                     args, user['tokens']['access_token'])
        finally:
            args.pop('p_pin', None)
        if not isinstance(value, dict) or type(value.get('available')) is not bool:
            raise DomainError('BACKUP_UNAVAILABLE', 503)
        if operation == 'restore' and value['available']:
            if not isinstance(value.get('pin'), str) or not re.fullmatch(r'[0-9]{4,16}', value['pin']):
                raise DomainError('BACKUP_UNAVAILABLE', 503)
            return {'available': True, 'pin': value['pin']}
        return {'available': value['available'], 'updated_at': value.get('updated_at')}


def mount_pin_backups(router, broker, agent):
    backups = PinBackups(broker)

    @router.post('/android/pin-backup/save')
    def save(body: SaveBackup, identity=Depends(agent)):
        return backups.call(identity, body, 'save')

    @router.post('/android/pin-backup/status')
    def status(body: BackupRequest, identity=Depends(agent)):
        return backups.call(identity, body, 'status')

    @router.post('/android/pin-backup/restore')
    def restore(body: BackupRequest, identity=Depends(agent)):
        return backups.call(identity, body, 'restore')

    @router.post('/android/pin-backup/remove')
    def remove(body: BackupRequest, identity=Depends(agent)):
        return backups.call(identity, body, 'remove')
