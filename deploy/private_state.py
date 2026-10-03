"""Initialize only StoryFX's private state. Never prints the generated key."""
import json
import os
from pathlib import Path
import secrets
import base64
import stat


def private_file(path, flags):
    descriptor = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError('PRIVATE_REGULAR_FILE_REQUIRED')
    os.fchmod(descriptor, 0o600)
    os.fchown(descriptor, 10000, 10000)
    return descriptor


def initialize(root=Path('/opt/formafx/storyfx/state')):
    if root.resolve() != Path('/opt/formafx/storyfx/state'):
        raise ValueError('STATE_TARGET_REFUSED')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    for name in ('session.key', 'app-config.json', 'storyfx.db', 'storyfx.db-wal', 'storyfx.db-shm'):
        if (root / name).is_symlink():
            raise ValueError('PRIVATE_SYMLINK_REFUSED')
    key = root / 'session.key'
    if not key.exists():
        descriptor = private_file(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(base64.urlsafe_b64encode(secrets.token_bytes(32)))
    else:
        os.close(private_file(key, os.O_RDONLY))
    config = root / 'app-config.json'
    expected = {'mode': 'private', 'origin': 'https://story.formafx.com'}
    if config.exists():
        with os.fdopen(private_file(config, os.O_RDONLY), 'r') as source:
            if json.load(source) != expected:
                raise ValueError('EXISTING_CONFIGURATION_MISMATCH')
    with os.fdopen(private_file(config, os.O_WRONLY | os.O_CREAT | os.O_TRUNC), 'w') as output:
        json.dump(expected, output)
    os.chown(root, 10000, 10000)


if __name__ == '__main__':
    initialize()
    print('private_state_ready=true\nsecret_printed=false')
