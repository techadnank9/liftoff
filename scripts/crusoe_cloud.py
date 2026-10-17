"""Tiny signed client for the Crusoe Cloud REST API (VMs for the NemoClaw sandbox).

    python scripts/crusoe_cloud.py GET /projects
    python scripts/crusoe_cloud.py GET /projects/<id>/compute/vms/types

Reads CRUSOE_ACCESS_KEY_ID and CRUSOE_SECRET_KEY from .env. Not a model call, so it
does not go through liftoff/llm.py; it never touches inference.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import certifi

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from liftoff import llm  # noqa: E402,F401  (loads .env)

BASE = os.environ.get("CRUSOE_API_BASE", "https://api.crusoecloud.com")
API = os.environ.get("CRUSOE_API_VERSION", "/v1alpha5")


def request(method: str, path: str, params: dict | None = None, body: dict | None = None):
    key, secret = os.environ["CRUSOE_ACCESS_KEY_ID"], os.environ["CRUSOE_SECRET_KEY"]
    query = "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    ts = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    payload = f"{API}{path}\n{query}\n{method}\n{ts}\n"
    raw = base64.urlsafe_b64decode(secret + "=" * (-len(secret) % 4))
    sig = base64.urlsafe_b64encode(hmac.new(raw, payload.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    url = BASE + API + path + (f"?{query}" if query else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "X-Crusoe-Timestamp": ts, "Authorization": f"Bearer 1.0:{key}:{sig}",
        "Content-Type": "application/json", "User-Agent": "liftoff/1.0 (crusoe-cloud-client)"})
    ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            text = r.read().decode()
            return r.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


if __name__ == "__main__":
    m, p = sys.argv[1], sys.argv[2]
    params = dict(a.split("=", 1) for a in sys.argv[3:]) if len(sys.argv) > 3 else None
    status, out = request(m, p, params)  # GET or DELETE from the CLI; POST bodies go through crusoe_vm.py
    print(status)
    print(json.dumps(out, indent=1) if isinstance(out, (dict, list)) else out)
