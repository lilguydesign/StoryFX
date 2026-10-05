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
                'android_publication_enabled': False}
    complete = isinstance(value, dict) and all(key in value for key in required)
    valid = complete and all(type(value[key]) is type(expected) and value[key] == expected
                             for key, expected in required.items())
    healthy = valid and value.get('status') == 'ok' and value.get('database_ok') is True
    return {'id': 'storyfx_control_plane', 'application': 'StoryFX',
            'status': 'ok' if healthy else 'incident' if complete else 'unknown',
            'reason_code': 'CONTROL_CONTRACT_OK' if healthy else 'CONTROL_CONTRACT_INVALID' if complete else 'CONTROL_PROOF_MISSING',
            'metrics': {'public_contract_verified': healthy, 'windows_executor_observed': False,
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
