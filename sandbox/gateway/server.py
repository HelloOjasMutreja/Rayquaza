import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from sandbox.gateway.chat import handle_chat


class Gateway:
    """Ollama-compatible local server. Serves POST /api/chat and GET /api/tags.

    /api/chat routes through the Router + Meter (handle_chat). /api/tags lists local
    Ollama models so the UI can populate its dropdown. Runs on a background thread.
    """

    def __init__(self, router, meter, ollama_url: str = "http://localhost:11434", port: int = 0):
        self._router = router
        self._meter = meter
        self._ollama_url = ollama_url.rstrip("/")
        self._httpd = ThreadingHTTPServer(("127.0.0.1", port), self._make_handler())
        self._thread = None

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/chat"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()

    def _make_handler(self):
        router, meter, ollama_url = self._router, self._meter, self._ollama_url

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence default stderr logging
                pass

            def _send(self, code, obj):
                body = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.startswith("/api/tags"):
                    try:
                        r = requests.get(ollama_url + "/api/tags", timeout=10)
                        self._send(200, r.json())
                    except Exception:
                        self._send(200, {"models": []})
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self):
                if not self.path.startswith("/api/chat"):
                    self._send(404, {"error": "not found"})
                    return
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                self._send(200, handle_chat(payload, router, meter))

        return Handler
