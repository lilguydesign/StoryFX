"""The Windows bridge retries acknowledgements, never publication actions."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

pytest.importorskip('msvcrt')
BRIDGE = Path(__file__).resolve().parents[2] / 'windows-bridge'
sys.path.insert(0, str(BRIDGE))
spec = importlib.util.spec_from_file_location('windows_bridge_main', BRIDGE / 'main.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class Api:
    def __init__(self):
        self.calls, self.fail = [], True

    def post(self, path, value):
        self.calls.append((path, value))
        if self.fail:
            raise OSError('synthetic-offline')
        return {'recorded': True}


def test_completed_phone_action_is_not_replayed_after_lost_ack(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, 'PRIVATE', tmp_path)
    executed = []
    def execute(*args):
        executed.append(True)
        return {'state': 'CONFIRMED', 'evidence': 'own_status_verified'}
    api = Api()
    job = {'id': '00000000-0000-0000-0000-000000000001', 'occurrence_id': 'a' * 64, 'payload': {'device': 'Validation technique'}}
    with pytest.raises(OSError):
        bridge.handle(api, job, {'Validation technique': {'enabled': True}}, execute)
    assert len(executed) == 1
    api.fail = False
    bridge.flush(api)
    assert len(executed) == 1
    assert list(tmp_path.glob('result-*.json')) == []
    assert json.loads((tmp_path / ('occurrence-' + 'a' * 64 + '.json')).read_text())['state'] == 'CONFIRMED'


def test_reserved_occurrence_after_crash_is_reviewed_without_phone_action(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, 'PRIVATE', tmp_path)
    identity = 'b' * 64
    (tmp_path / ('occurrence-' + identity + '.json')).write_text(json.dumps({'state': 'NEEDS_REVIEW', 'evidence': 'result_uncertain'}))
    api = Api(); api.fail = False
    def no_action(*args):
        raise AssertionError('PUBLICATION_MUST_NOT_REPLAY')
    bridge.handle(api, {'id': '00000000-0000-0000-0000-000000000002', 'occurrence_id': identity,
                        'payload': {'device': 'Validation technique'}}, {'Validation technique': {}}, no_action)
    assert api.calls[-1][1]['state'] == 'NEEDS_REVIEW'


def test_unsupported_platform_refused_before_any_phone_connection():
    from publication_adapter import execute
    assert execute(None, None, {'platform': 'Facebook', 'engine': 'multi', 'count': 3}, {}) == {
        'state': 'FAILED_BEFORE_PUBLICATION', 'evidence': 'preflight_refused'}
