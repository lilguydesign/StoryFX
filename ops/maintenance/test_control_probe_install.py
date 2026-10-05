"""The additive patch is closed, idempotent and rejects incompatible collectors."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('control_install', Path(__file__).with_name('install_control_probe.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_patch_preserves_other_checks_and_is_idempotent():
    source = ('from storyfx_public_probe import collect_storyfx_public_checks\n'
              'def collect(now):\n    checks=[]\n'
              '    checks.extend(collect_storyfx_public_checks(now=now))\n    return checks\n')
    changed = module.patch(source)
    assert module.patch(changed) == changed
    assert changed.replace('\n' + module.IMPORT, '').replace('\n' + module.CALL, '') == source


def test_partial_or_incompatible_collector_is_refused():
    for source in ('', module.IMPORT, module.CALL):
        with pytest.raises(RuntimeError):
            module.patch(source)
