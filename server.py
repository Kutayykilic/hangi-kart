"""Yerel web sunucusu.  python3 server.py  ->  http://localhost:8000

- web/ klasörünü servis eder
- /data/campaigns.json : kampanya verisi
- POST /api/refresh     : kampanyaları arka planda yeniden çeker
- GET  /api/status      : yenileme durumu
"""
import json
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
state = {"running": False, "last_error": None}


def refresh():
    state["running"], state["last_error"] = True, None
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scraper" / "scrape.py")],
                           capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            state["last_error"] = r.stderr[-500:]
    except Exception as e:  # noqa: BLE001
        state["last_error"] = str(e)
    finally:
        state["running"] = False


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        clean = path.split("?")[0]
        if clean.startswith("/data/"):
            return str(ROOT / clean.lstrip("/"))
        return str(ROOT / "web" / clean.lstrip("/"))

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/status"):
            return self._json(state)
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/refresh"):
            if not state["running"]:
                threading.Thread(target=refresh, daemon=True).start()
            return self._json({"started": True})
        self.send_error(404)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if not (ROOT / "data" / "campaigns.json").exists():
        print("İlk çalıştırma: kampanyalar çekiliyor (~1-2 dk)...")
        refresh()
    print(f"Hazır: http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
