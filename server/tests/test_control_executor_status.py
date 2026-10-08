"""Dispatch explanations must preserve the exact executor and no-send contract."""
import pytest
from storyfx_server.control_executor_status import executor_wait_reason, scheduler_wait_reason
from storyfx_server.control_android import executors


VALUE = dict(device='Validation technique', platform='WhatsApp', engine='intro+multi',
             count=11, album='Validation technique introduction', album2='Validation technique')
NATIVE = dict(profiles=['Validation technique'], connected=True,
              executor='android_whatsapp_images_v1', media_modes_ready=False)


@pytest.mark.parametrize('node,reason', [
    (NATIVE, 'ANDROID_MEDIA_CAPABILITY_REQUIRED'),
    ({**NATIVE, 'connected': False}, 'ANDROID_DISCONNECTED'),
    ({**NATIVE, 'connected': False, 'wait_reason': 'SCREEN_LOCKED'}, 'SCREEN_LOCKED'),
    ({**NATIVE, 'connected': False, 'wait_reason': 'DISABLED'}, 'ANDROID_EXECUTOR_DISABLED'),
    ({**NATIVE, 'connected': False, 'wait_reason': 'GLOBAL_AGENT_DISABLED'}, 'ANDROID_EXECUTOR_DISABLED'),
    ({**NATIVE, 'connected': False, 'wait_reason': 'ACCESSIBILITY_REQUIRED'}, 'ACCESSIBILITY_REQUIRED'),
    ({**NATIVE, 'media_modes_ready': True}, 'READY'),
])
def test_native_waits_are_not_reported_as_windows_failure(node, reason):
    snapshot = {'nodes': [node]}
    before = executors(snapshot, VALUE)
    assert executor_wait_reason(snapshot, VALUE) == reason
    assert executors(snapshot, VALUE) == before
    assert bool(before) == (reason == 'READY')


def test_unsupported_facebook_and_tiktok_are_distinct_from_disconnection():
    for platform in ('Facebook', 'TikTok'):
        assert executor_wait_reason({'nodes': [NATIVE]}, {**VALUE, 'platform': platform}) == 'ADAPTER_NOT_VALIDATED'
    assert executor_wait_reason({'nodes': []}, VALUE) == 'WINDOWS_DISCONNECTED'


def test_conflicting_executors_and_multiple_waits_stay_ineligible():
    node = {**NATIVE, 'media_modes_ready': True}
    assert executor_wait_reason({'nodes': [node, node]}, VALUE) == 'EXECUTOR_CONFLICT'
    assert scheduler_wait_reason({'nodes': [NATIVE]}, [VALUE]) == 'ANDROID_MEDIA_CAPABILITY_REQUIRED'
    other = {**VALUE, 'device': 'Validation technique autre'}
    assert scheduler_wait_reason({'nodes': [NATIVE]}, [VALUE, other]) == 'MULTIPLE_EXECUTOR_WAITS'
    assert scheduler_wait_reason({'nodes': [node]}, [VALUE]) == ''
