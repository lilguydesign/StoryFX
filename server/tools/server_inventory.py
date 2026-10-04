"""Read-only remote deployment inventory. Do not inspect container environments."""
import json
from pathlib import Path
import re
import subprocess


proxy = 'formafx-public-api-caddy'
networks = json.loads(subprocess.check_output(['docker', 'inspect', proxy, '--format', '{{json .NetworkSettings.Networks}}']))
mode = subprocess.check_output(['docker', 'inspect', proxy, '--format', '{{.HostConfig.NetworkMode}}']).decode().strip()
print(json.dumps({'proxy_networks': list(networks),
                  'proxy_network_mode': mode,
                  'storyfx_exists': Path('/opt/formafx/storyfx').exists()}))
config = Path('/opt/formafx/public-api-caddy/Caddyfile').read_text()
for line in config.splitlines():
    if re.match(r'^\s*[a-zA-Z0-9.-]+\.formafx\.com\s*\{', line):
        print(line.strip())
    elif re.match(r'^\s*reverse_proxy\s+[a-zA-Z0-9.:_-]+\s*$', line):
        print(line.strip())
