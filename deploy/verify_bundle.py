"""Validate the actual deployable shell bytes produced from the Git commit."""
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def verify(archive):
    shell = 'bash'
    if sys.platform == 'win32':
        shell = r'C:\Program Files\Git\bin\bash.exe'
    with tarfile.open(archive) as source, tempfile.TemporaryDirectory() as folder:
        for member in source.getmembers():
            if not member.isfile() or not member.name.endswith('.sh'):
                continue
            contents = source.extractfile(member).read()
            assert b'\r' not in contents, 'LINUX_SCRIPT_LINE_ENDINGS_REFUSED'
            target = Path(folder) / Path(member.name).name
            target.write_bytes(contents)
            subprocess.run([shell, '-n', str(target)], check=True)
    print('archived_linux_scripts_valid=true')


if __name__ == '__main__':
    verify(sys.argv[1])
