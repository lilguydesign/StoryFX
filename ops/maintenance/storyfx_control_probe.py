"""Read-only control-plane contract. Does not assert private executor availability."""
import json
import urllib.error
import urllib.request

URL = 'https://story.formafx.com/health'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def evaluate(value):
    required = {'control_center_mode': 'windows_bridge', 'windows_publication_enabled': True,
                'scheduler_available': True,
                'scheduler_worker_ok': True, 'scheduler_tick_seconds': 10}
    complete = isinstance(value, dict) and all(key in value for key in (*required, 'android_publication_enabled'))
    valid = complete and all(type(value[key]) is type(expected) and value[key] == expected
                             for key, expected in required.items())
    android = complete and (value['android_publication_enabled'] is False and not value.get('android_executor')
                            or value['android_publication_enabled'] is True and value.get('android_executor') == 'whatsapp_images_pilot')
    recovery_keys = ('manual_android_retry_available', 'publication_failure_stages')
    recovery_verified = complete and all(value.get(key) is True for key in recovery_keys)
    recovery = complete and (not any(key in value for key in recovery_keys) or recovery_verified)
    unlock_keys = ('local_android_unlock_available', 'empty_status_review_available')
    unlock_verified = complete and all(value.get(key) is True for key in unlock_keys)
    unlock = complete and (not any(key in value for key in unlock_keys) or unlock_verified)
    media_keys = ('android_media_modes', 'android_media_modes_min_version')
    media_verified = complete and value.get('android_media_modes') == ['intro', 'multi', 'intro+multi'] and value.get('android_media_modes_min_version') == '0.4.13'
    media = complete and (not any(key in value for key in media_keys) or media_verified)
    healthy = valid and android and recovery and unlock and media and value.get('status') == 'ok' and value.get('database_ok') is True
    return {'id': 'storyfx_control_plane', 'application': 'StoryFX',
            'label': 'StoryFX — commandes web',
            'detail': 'Contrat HTTPS Windows et pilote Android ; disponibilité des téléphones et publication non observées.',
            'status': 'ok' if healthy else 'incident' if complete else 'unknown',
            'reason_code': 'CONTROL_CONTRACT_OK' if healthy else 'CONTROL_CONTRACT_INVALID' if complete else 'CONTROL_PROOF_MISSING',
            'metrics': {'public_contract_verified': healthy, 'windows_executor_observed': False,
                        'android_executor_observed': False, 'android_reboot_verified': False,
                        'manual_retry_contract_verified': bool(recovery_verified),
                        'local_unlock_contract_verified': bool(unlock_verified),
                        'media_mode_contract_verified': bool(media_verified),
                        'publication_verified': False, 'phone_actions': False},
            'notifications_sent': False, 'business_mutations': False}


def collect():
    request = urllib.request.Request(URL, headers={'Accept': 'application/json', 'Cache-Control': 'no-cache'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=8) as response:
            if response.geturl() != URL or response.status != 200:
                raise ValueError('PUBLIC_CONTRACT_REFUSED')
            body = response.read(16385)
            if len(body) > 16384:
                raise ValueError('BODY_TOO_LARGE')
            return evaluate(json.loads(body))
    except (OSError, ValueError, urllib.error.URLError):
        return evaluate(None)


if __name__ == '__main__':
    print(json.dumps(collect()))
