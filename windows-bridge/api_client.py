"""Only the official HTTPS origin; no redirects or credentials in URLs."""
import json
import urllib.request

ORIGIN = 'https://story.formafx.com'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Api:
    def __init__(self, credential=None):
        self.credential = credential
        self.opener = urllib.request.build_opener(NoRedirect)

    def post(self, path, value):
        if not path.startswith('/v1/control/windows/') or '..' in path or '?' in path:
            raise ValueError('BRIDGE_ROUTE_REFUSED')
        headers = {'Content-Type': 'application/json'}
        if self.credential:
            headers['Authorization'] = 'Bearer ' + self.credential
        request = urllib.request.Request(ORIGIN + path, json.dumps(value).encode(), headers, method='POST')
        with self.opener.open(request, timeout=20) as response:
            content = response.read(2 * 1024 * 1024 + 1)
            if len(content) > 2 * 1024 * 1024:
                raise ValueError('RESPONSE_TOO_LARGE')
            return json.loads(content)
