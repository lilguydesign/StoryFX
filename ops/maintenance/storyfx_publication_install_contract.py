"""Narrow collector integration; callers own deployment, preimages and rollback."""
import ast

IMPORT = 'from storyfx_publication_probe import collect as collect_storyfx_publication'
CALL = '    checks.append(collect_storyfx_publication(now))'
ANCHOR = 'from storyfx_public_probe import collect_storyfx_public_checks'
INVOCATION = '    checks.extend(collect_storyfx_public_checks(now=now))'


def patch(text):
    if text.count(IMPORT) == 1 and text.count(CALL) == 1:
        ast.parse(text)
        return text
    if IMPORT in text or CALL in text:
        raise ValueError('PARTIAL_STORYFX_PUBLICATION_INTEGRATION')
    if text.count(ANCHOR) != 1 or text.count(INVOCATION) != 1:
        raise ValueError('STORYFX_PUBLICATION_ANCHOR_CHANGED')
    changed = text.replace(ANCHOR, ANCHOR + '\n' + IMPORT).replace(INVOCATION, INVOCATION + '\n' + CALL)
    ast.parse(changed)
    if changed.replace('\n' + IMPORT, '').replace('\n' + CALL, '') != text:
        raise ValueError('STORYFX_PUBLICATION_SCOPE_CHANGED')
    return changed
