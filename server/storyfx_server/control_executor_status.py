"""Explain dispatch readiness without changing eligibility, claims or scheduling."""
from .control_android import executors
from .control_media_modes import supported_media, requires_media_v2


def executor_wait_reason(snapshot, value):
    if not supported_media(value):
        return 'ADAPTER_NOT_VALIDATED'
    eligible = executors(snapshot, value)
    if len(eligible) == 1:
        return 'READY'
    if len(eligible) > 1:
        return 'EXECUTOR_CONFLICT'
    native = [node for node in snapshot['nodes'] if value['device'] in node['profiles']
              and node.get('executor') == 'android_whatsapp_images_v1']
    if len(native) > 1:
        return 'EXECUTOR_CONFLICT'
    if native:
        node = native[0]
        reason = node.get('wait_reason', '')
        if reason in {'DISABLED', 'GLOBAL_AGENT_DISABLED'}:
            return 'ANDROID_EXECUTOR_DISABLED'
        if reason in {'SCREEN_LOCKED', 'ACCESSIBILITY_REQUIRED', 'MEDIA_PERMISSION_REQUIRED',
                      'WAITING_PERMISSIONS'}:
            return reason
        if node.get('connected') and requires_media_v2(value) and not node.get('media_modes_ready'):
            return 'ANDROID_MEDIA_CAPABILITY_REQUIRED'
        return 'ANDROID_DISCONNECTED'
    return 'WINDOWS_DISCONNECTED'


def scheduler_wait_reason(snapshot, selected):
    reasons = {executor_wait_reason(snapshot, value) for value in selected}
    reasons.discard('READY')
    if not reasons:
        return ''
    return next(iter(reasons)) if len(reasons) == 1 else 'MULTIPLE_EXECUTOR_WAITS'
