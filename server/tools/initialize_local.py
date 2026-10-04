"""Create a local diagnostic credential without displaying it."""
from pathlib import Path
import os
import secrets
import getpass
import subprocess


def initialize():
    root = Path(__file__).resolve().parents[2]
    state = root / '.runtime' / 'private'
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'nt':
        subprocess.run(['icacls', str(state), '/inheritance:r', '/grant:r',
                        getpass.getuser() + ':(OI)(CI)F', '/grant:r', 'SYSTEM:(OI)(CI)F'],
                       check=True, capture_output=True)
    credential = state / 'owner.credential'
    if not credential.exists():
        with credential.open('x', encoding='utf-8') as stream:
            stream.write(secrets.token_urlsafe(48))
        if os.name != 'nt':
            credential.chmod(0o600)
    print('Local diagnostic credential configured; value not displayed.')
    print('Bind only to 127.0.0.1. Internet deployment needs HTTPS and account authentication.')


if __name__ == '__main__':
    initialize()
