"""Evaluate a trusted live loopback response using the canonical read-only probe."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import httpx


def main():
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / 'ops' / 'maintenance'))
    from storyfx_diagnostics_probe import evaluate
    credential = (root / '.runtime' / 'private' / 'owner.credential').read_text().strip()
    with httpx.Client(base_url='http://127.0.0.1:18743', timeout=10) as client:
        health = client.get('/health').json()
        dashboard = client.get('/v1/dashboard', headers={'Authorization': 'Bearer ' + credential}).json()
    now = datetime.now(timezone.utc)
    result = evaluate(health, dashboard, observed_at=now, now=now)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
