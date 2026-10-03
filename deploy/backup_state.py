"""Copy stopped StoryFX SQLite state without following service-controlled symlinks."""
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys


def backup(destination):
    source = Path('/opt/formafx/storyfx/state')
    destination = Path(destination)
    assert source.resolve() == source
    assert destination.resolve().parent == Path('/opt/formafx/storyfx/backups')
    assert destination.is_dir() and not destination.is_symlink()
    for name in ('storyfx.db', 'storyfx.db-wal', 'storyfx.db-shm'):
        path = source / name
        if not path.exists() and not path.is_symlink():
            continue
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise ValueError('DATABASE_REGULAR_FILE_REQUIRED')
        with os.fdopen(descriptor, 'rb') as incoming, (destination / name).open('xb') as output:
            shutil.copyfileobj(incoming, output)
        (destination / name).chmod(0o600)
    if (destination / 'storyfx.db').exists():
        with sqlite3.connect(destination / 'storyfx.db') as database:
            assert database.execute('PRAGMA quick_check').fetchone()[0] == 'ok'


if __name__ == '__main__':
    backup(sys.argv[1])
    print('database_backup_verified=true')
