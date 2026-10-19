"""Exercise the real local frontend server without injecting browser API settings."""

from __future__ import annotations

import importlib.util
import json
from contextlib import contextmanager
from functools import partial
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

MODULE = Path(__file__).resolve().parents[2] / "scripts" / "serve_demo.py"
spec = importlib.util.spec_from_file_location("serve_demo", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@contextmanager
def running_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def request(port, method, path, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


class EchoBackend(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", "demo_session=test; HttpOnly; Path=/; SameSite=Strict")
        self.end_headers()
        self.wfile.write(
            json.dumps({"path": self.path, "cookie": self.headers.get("Cookie"), "body": payload.decode()}).encode()
        )

    def do_GET(self):
        self.send_response(503 if self.path == "/health" else 200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"degraded"}')


def test_custom_port_serves_assets_and_proxies_api_and_session(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Workbench</h1>", encoding="utf-8")
    with running_server(EchoBackend) as backend:
        handler = partial(module.DemoHandler, backend_port=backend, directory=str(tmp_path))
        with running_server(handler) as frontend:
            assert request(frontend, "GET", "/")[2] == b"<h1>Workbench</h1>"
            status, headers, body = request(
                frontend, "POST", "/api/plans?draft=1", '{"units":12}', {"Cookie": "demo_session=existing"}
            )
            assert status == 201
            assert "HttpOnly" in headers["Set-Cookie"]
            assert json.loads(body) == {
                "path": "/api/plans?draft=1",
                "cookie": "demo_session=existing",
                "body": '{"units":12}',
            }
            assert request(frontend, "GET", "/health")[0] == 503
            assert request(frontend, "POST", "/index.html", "x")[0] == 405
            assert (
                request(frontend, "POST", "/api/upload", headers={"Content-Length": str(module.MAX_BODY_BYTES + 1)})[0]
                == 413
            )


def test_backend_outage_has_an_actionable_json_error(tmp_path):
    reserved = ThreadingHTTPServer(("127.0.0.1", 0), EchoBackend)
    backend_port = reserved.server_port
    reserved.server_close()
    handler = partial(module.DemoHandler, backend_port=backend_port, directory=str(tmp_path))
    with running_server(handler) as frontend:
        status, _, body = request(frontend, "GET", "/api/products")
        assert status == 502
        assert "restart" in json.loads(body)["error"]["message"]
