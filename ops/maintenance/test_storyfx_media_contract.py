"""The public capability contract never proves a private media publication."""
from storyfx_control_probe import evaluate


def test_media_capability_requires_both_fields_and_never_claims_delivery():
    value = {'status': 'ok', 'database_ok': True, 'control_center_mode': 'windows_bridge',
             'windows_publication_enabled': True, 'scheduler_available': True, 'scheduler_worker_ok': True,
             'scheduler_tick_seconds': 10, 'android_publication_enabled': True, 'android_executor': 'whatsapp_images_pilot',
             'android_media_modes': ['intro', 'multi', 'intro+multi'], 'android_media_modes_min_version': '0.4.13'}
    result = evaluate(value)
    assert result['status'] == 'ok' and result['metrics']['media_mode_contract_verified']
    assert not result['metrics']['publication_verified'] and not result['notifications_sent']
    assert evaluate({**value, 'android_media_modes_min_version': '0.4.12'})['status'] == 'incident'
    del value['android_media_modes_min_version']
    assert evaluate(value)['status'] == 'incident'
