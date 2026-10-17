"""Serve the landing page at / (site/index.html) with its images from docs/.

    python scripts/serve_site.py            # http://localhost:3000
    python scripts/serve_site.py 3000 http://localhost:8501   # port, mission control URL

Mission control (streamlit run app.py) runs separately, on 8501 by default.
"""
from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3000


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean in ("/", "/index.html"):
            return str(ROOT / "site" / "index.html")
        if clean.startswith("/docs/"):
            return str(ROOT / clean.lstrip("/"))
        return str(ROOT / "site" / clean.lstrip("/"))

    def log_message(self, fmt: str, *args) -> None:  # quiet
        pass


if __name__ == "__main__":
    print(f"Liftoff landing page on http://localhost:{PORT}")
    ThreadingHTTPServer(("", PORT), partial(Handler, directory=str(ROOT))).serve_forever()
