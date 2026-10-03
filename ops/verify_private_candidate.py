"""Validate the exact StoryFX changed paths before selecting this milestone."""
import ast
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {'.py', '.kt', '.kts', '.js', '.ts', '.css', '.html', '.ps1', '.sh', '.yaml', '.yml'}


def git(*args):
    return subprocess.check_output(['git', '-c', 'safe.directory=' + str(ROOT), *args], cwd=ROOT, text=True).splitlines()


def main():
    assert not git('diff', '--cached', '--name-only'), 'EXISTING_INDEX_REFUSED'
    paths = sorted(set(git('diff', '--name-only') + git('ls-files', '--others', '--exclude-standard')))
    allowed = ('server/', 'dashboard/', 'android-agent/', 'deploy/', 'supabase/', 'docs/PRIVATE_PILOT.md',
               '.github/workflows/storyfx-foundation.yml', 'ops/Set-StoryFXWorkLogin.ps1',
               'ops/format_login_css.py', 'ops/upgrade_dashboard_accounts.py', 'ops/verify_private_candidate.py')
    counts = {}
    for name in paths:
        path = ROOT / name
        assert name.startswith(allowed), 'UNEXPECTED_CHANGED_PATH:' + name
        assert not any(part in {'.runtime', '.secrets', '.env', 'node_modules', 'build', '__pycache__'} for part in path.relative_to(ROOT).parts)
        if path.suffix not in SOURCE:
            continue
        text = path.read_text(encoding='utf-8-sig')
        counts[name] = len(text.splitlines())
        assert counts[name] <= 300, 'SOURCE_TOO_LONG:' + name
        assert not re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', text), 'PRIVATE_KEY_REFUSED'
        assert not re.search(r'(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}', text), 'PRIVATE_TOKEN_REFUSED'
        assert not re.search(r'\b(?:sk-proj-|sk_live_)[A-Za-z0-9_-]{20,}', text), 'PRIVATE_TOKEN_REFUSED'
        if path.suffix == '.py':
            ast.parse(text)
    report = {'candidate_files': paths, 'line_counts': counts, 'index_initially_empty': True,
              'private_file_scan': 'passed', 'tracked_secrets_found': False}
    target = ROOT / '.runtime' / 'deploy' / 'candidate-validation.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2))
    print(json.dumps({'files': len(paths), 'manual_sources': len(counts), 'max_lines': max(counts.values()),
                      'private_file_scan': 'passed', 'report': str(target)}))


if __name__ == '__main__':
    main()
