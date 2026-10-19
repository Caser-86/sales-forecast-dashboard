"""Serve the local workbench and proxy its API on one loopback origin."""

from __future__ import annotations

import argparse
import http.client
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
MAX_BODY_BYTES = 16 * 1024 * 1024
HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, backend_port: int, **kwargs):
        self.backend_port = backend_port
        super().__init__(*args, **kwargs)

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Browsers cancel in-flight requests when filters or routes change.
            pass

    def _json_error(self, status: int, message: str) -> None:
        body = json.dumps({"error": {"message": message}}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _handle(self) -> None:
        path = urlsplit(self.path).path
        if path != "/health" and path != "/api" and not path.startswith("/api/"):
            if self.command in {"GET", "HEAD"}:
                return getattr(super(), f"do_{self.command}")()
            return self._json_error(405, "Only API endpoints accept write requests.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._json_error(400, "Invalid Content-Length.")
        if self.headers.get("Transfer-Encoding") or length < 0:
            return self._json_error(400, "A non-negative Content-Length is required.")
        if length > MAX_BODY_BYTES:
            return self._json_error(413, "Request exceeds the local demo upload limit (16 MiB).")
        body = self.rfile.read(length) if length else None
        blocked = HOP_HEADERS | {"host", "content-length"}
        blocked.update(value.strip().lower() for value in self.headers.get("Connection", "").split(","))
        headers = {key: value for key, value in self.headers.items() if key.lower() not in blocked}
        connection = http.client.HTTPConnection("127.0.0.1", self.backend_port, timeout=30)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            response_headers = response.getheaders()
        except (OSError, http.client.HTTPException):
            return self._json_error(502, "Backend unavailable. Check the demo service logs and restart.")
        finally:
            connection.close()
        self.send_response(response.status)
        blocked_response = HOP_HEADERS | {"content-length", "server", "date"}
        blocked_response.update(value.strip().lower() for value in response.getheader("Connection", "").split(","))
        for key, value in response_headers:
            if key.lower() not in blocked_response:
                self.send_header(key, value)
        self.send_header(
            "Content-Length", response.getheader("Content-Length", "0") if self.command == "HEAD" else str(len(payload))
        )
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _handle

    def list_directory(self, path):
        self.send_error(404, "Directory listing is disabled.")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--backend-port", type=int, default=8000)
    args = parser.parse_args()
    handler = partial(DemoHandler, backend_port=args.backend_port, directory=str(FRONTEND))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
