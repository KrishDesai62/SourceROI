"""Zero-dependency localhost web UI and JSON API."""
from __future__ import annotations
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from .corpus import load_project
from .evaluation import ablation_study, change_report, evaluate, differences, optimize_portfolio
from .store import read_baseline, save_baseline

WEB = Path(__file__).parent / "web"
MAX_BODY_BYTES = 64_000


def serve(host: str = "127.0.0.1", port: int = 8765, project_path: str | None = None):
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("SourceROI prototype binds to localhost only (for safety).")

    class Handler(BaseHTTPRequestHandler):
        server_version = "SourceROI/0.1"

        def _send_json(self, body: dict, code: int = 200):
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= MAX_BODY_BYTES:
                raise ValueError("Request too large")
            return json.loads(self.rfile.read(length) or b"{}")

        def _boundary(self):
            from .live.http_guard import validate_browser_request
            if not validate_browser_request(self.headers.get('Host', ''), self.headers.get('Origin')):
                self._send_json({'error': 'Host or Origin not permitted'}, 403)
                return False
            return True

        def do_GET(self):
            if not self._boundary(): return
            parsed = urlparse(self.path)
            if parsed.path == "/api/state":
                try:
                    p = load_project(project_path)
                    report = evaluate(p)
                    saved = read_baseline(p)
                    delta = change_report(saved, report, p) if saved else None
                    self._send_json({
                        "project": {k: p[k] for k in ("id", "name", "description")},
                        "sources": p["sources"],
                        "documents": [{k: d[k] for k in ("id", "title", "source_id", "path", "word_count", "fingerprint")}
                                      for d in p["documents"]],
                        "report": report,
                        "ablations": ablation_study(p, report),
                        "portfolio": {str(floor): optimize_portfolio(p, floor) for floor in (.75, .85, .95, 1.0)},
                        "baseline": delta,
                        "has_baseline": saved is not None,
                    })
                except Exception as exc:
                    self._send_json({"error": str(exc)}, 400)
                return
            if parsed.path.startswith("/api/document/"):
                try:
                    identifier = unquote(parsed.path[len("/api/document/"):])
                    doc = next(d for d in load_project(project_path)["documents"] if d["id"] == identifier)
                    self._send_json({"id": doc["id"], "title": doc["title"], "path": doc["path"],
                                     "source_id": doc["source_id"], "content": doc["content"]})
                except (StopIteration, ValueError, FileNotFoundError) as exc:
                    self._send_json({"error": str(exc) or "Document not found"}, 404)
                return
            target = parsed.path if parsed.path not in ("", "/") else "/index.html"
            # Static frontend assets only. Prevent traversal and hidden files.
            path = (WEB / target.lstrip("/")).resolve()
            if not path.is_relative_to(WEB.resolve()) or not path.is_file() or path.suffix not in (".html", ".css", ".js"):
                self.send_error(404)
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not self._boundary(): return
            try:
                payload = self._read_json()
                p = load_project(project_path)
                if self.path == "/api/compare":
                    excluded = set(payload.get("exclude_sources", []))
                    if not excluded.issubset({s["id"] for s in p["sources"]}):
                        raise ValueError("Unknown source ID")
                    base = evaluate(p)
                    alternate = evaluate(p, exclude_sources=excluded)
                    self._send_json({"baseline": base, "alternate": alternate,
                                     "diff": differences(base, alternate)})
                    return
                if self.path == "/api/save-baseline":
                    current = evaluate(p)
                    filepath = save_baseline(p, current)
                    self._send_json({"ok": True, "path": filepath})
                    return
                self._send_json({"error": "Unknown endpoint"}, 404)
            except (ValueError, TypeError, json.JSONDecodeError, FileNotFoundError) as exc:
                self._send_json({"error": str(exc)}, 400)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"\nSourceROI dashboard: http://{host}:{port}\nProject: {project_path or 'examples/finance'}")
    print("No dependencies or API key required. Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
