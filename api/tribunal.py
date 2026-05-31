from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.agent_swarm import run_tribunal

load_dotenv(ROOT / ".env")

TRIBUNAL_CACHE = Path("/tmp/aegis_last_tribunal.json")


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    return json.loads(raw or "{}")


def _fallback_payload() -> dict:
    return run_tribunal("NVDA", "Fallback export-control incident", 0.76, "critical")


def handle(payload: dict[str, Any]) -> dict:
    return run_tribunal(
        ticker=str(payload.get("ticker") or "NVDA"),
        incident=str(payload.get("incident") or payload.get("description") or "Unspecified crisis incident"),
        chaos_index=float(payload.get("chaos_index") or 0.5),
        severity=str(payload.get("severity") or "watch"),
    )


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        _json_response(self, {"ok": True})

    def do_GET(self) -> None:
        try:
            if TRIBUNAL_CACHE.exists():
                cached = json.loads(TRIBUNAL_CACHE.read_text())
                _json_response(self, {**cached, "cached": True})
            else:
                _json_response(self, {"cached": False})
        except Exception:
            _json_response(self, {"cached": False})

    def do_POST(self) -> None:
        try:
            _json_response(self, handle(_read_json(self)))
        except Exception:
            _json_response(self, _fallback_payload(), 200)
