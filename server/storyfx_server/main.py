"""Local factory. Credential read from an ignored private file, never a CLI argument."""
import os
import json
from pathlib import Path
from .api import create_app


def app_factory():
    root = Path(__file__).resolve().parents[2]
    state = Path(os.environ.get('STORYFX_STATE_DIR', str(root / '.runtime' / 'private')))
    config = state / 'app-config.json'
    if config.is_file():
        settings = json.loads(config.read_text())
        if settings.get('mode') != 'private' or settings.get('origin') != 'https://story.formafx.com':
            raise RuntimeError('PRIVATE_CONFIGURATION_INVALID')
        from .auth_client import AuthClient
        return create_app(state / 'storyfx.db', None, auth_client=AuthClient.discover(),
                          encryption_key=(state / 'session.key').read_bytes(), origin=settings['origin'])
    token_file = state / 'owner.credential'
    if not token_file.is_file():
        raise RuntimeError('Run the local initializer before starting StoryFX.')
    token = token_file.read_text(encoding='utf-8').strip()
    legacy = root / 'transmission' / 'StoryFX_Transmission_20261003_130046' / 'windows' / 'config'
    return create_app(state / 'storyfx.db', token, legacy_config=legacy if legacy.is_dir() else None)
