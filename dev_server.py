import json
import os
import sys
import mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Add root directory to sys.path so api modules can import from lib
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import api modules
try:
    import api.watchtower as watchtower
    import api.tribunal as tribunal
    import api.valuation as valuation
    import api.llm_patch as llm_patch
except ImportError as e:
    print(f"Error importing API modules: {e}")
    sys.exit(1)

class DevRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def do_OPTIONS(self):
        self._send_json({"ok": True})

    def do_GET(self):
        # Handle API GET requests
        if self.path == "/api/watchtower":
            cached = watchtower._load_cache()
            if cached:
                self._send_json({**cached, "cached": True})
            else:
                self._send_json({"incidents": [], "macro": {}, "cached": False})
            return
        elif self.path == "/api/tribunal":
            try:
                if tribunal.TRIBUNAL_CACHE.exists():
                    cached = json.loads(tribunal.TRIBUNAL_CACHE.read_text())
                    self._send_json({**cached, "cached": True})
                else:
                    self._send_json({"cached": False})
            except Exception:
                self._send_json({"cached": False})
            return

        # Handle static files
        clean_path = self.path.lstrip("/")
        if not clean_path or clean_path == "":
            file_path = ROOT / "index.html"
        else:
            # Strip query params or hash if any
            clean_path = clean_path.split("?")[0].split("#")[0]
            file_path = ROOT / clean_path

        # If file doesn't exist or is a directory, fallback to index.html (SPA routing)
        if not file_path.is_file():
            file_path = ROOT / "index.html"

        # Serve static file
        try:
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"
            
            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error serving file: {e}".encode("utf-8"))

    def do_POST(self):
        # Route API post requests
        if self.path == "/api/watchtower":
            try:
                payload = self._read_json()
                res = watchtower.handle(payload)
                self._send_json(res)
            except Exception as e:
                self._send_json({
                    "incidents": [watchtower.failure_incident("UNKNOWN", e)],
                    "macro": {"vix": 0.0, "scan_timestamp": watchtower.utc_timestamp()},
                })
        elif self.path == "/api/tribunal":
            try:
                payload = self._read_json()
                res = tribunal.handle(payload)
                self._send_json(res)
            except Exception as e:
                self._send_json(tribunal._fallback_payload())
        elif self.path == "/api/valuation":
            try:
                payload = self._read_json()
                res = valuation.handle(payload)
                self._send_json(res)
            except Exception as e:
                self._send_json(valuation.compute_valuation("NVDA", valuation.DEFAULT_ASSUMPTIONS))
        elif self.path == "/api/llm_patch":
            try:
                payload = self._read_json()
                res = llm_patch.handle(payload)
                self._send_json(res)
            except Exception as e:
                self._send_json(llm_patch.handle({}))
        else:
            self.send_response(404)
            self.end_headers()

def run(port=3000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, DevRequestHandler)
    print(f"\n========================================================")
    print(f" Aegis Codex Local Dev Server Started!")
    print(f" URL: http://localhost:{port}")
    print(f"========================================================\n")
    print("Press Ctrl+C to stop the server.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aegis Codex Local Dev Server")
    parser.add_argument("--port", type=int, default=3000, help="Port to run the server on")
    args = parser.parse_args()
    run(port=args.port)
