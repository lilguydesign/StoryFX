"""Split the new login stylesheet into readable, independent CSS modules."""
from pathlib import Path
import re


root = Path(__file__).resolve().parents[1] / 'dashboard' / 'login'
source = (root / 'login.css').read_text()
main, responsive = source.split('@media', 1)
blocks = []
for match in re.finditer(r'([^{}]+)\{([^{}]*)\}', main):
    selector, body = match.groups()
    lines = [selector.strip() + ' {']
    lines += ['  ' + declaration.strip() + ';' for declaration in body.split(';') if declaration.strip()]
    blocks.append('\n'.join(lines + ['}', '']))
chunks, current = [], []
for block in blocks:
    if sum(len(item.splitlines()) + 1 for item in current) + len(block.splitlines()) > 240:
        chunks.append('\n'.join(current))
        current = []
    current.append(block)
chunks.append('\n'.join(current))
names = ('login-layout.css', 'login-controls.css', 'login-details.css')
if len(chunks) != len(names):
    raise RuntimeError('CSS_MODULE_BOUNDARY_REVIEW_REQUIRED')
for name, chunk in zip(names, chunks):
    (root / name).write_text(chunk)
(root / 'login.css').write_text('\n'.join(f'@import url("./{name}");' for name in names) + '\n@media' + responsive)
print('login_css_modules=3')
