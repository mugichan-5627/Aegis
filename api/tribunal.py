from __future__ import annotations

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from lib.agent_swarm import run_tribunal, _fallback

def _get_cache_path(filename: str) -> Path:
    p = Path(f"/tmp/{filename}")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        test_file = p.parent / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        return p
    except Exception:
        fallback = ROOT / "tmp" / filename
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback

TRIBUNAL_CACHE = _get_cache_path("aegis_last_tribunal.json")

_STATIC_FALLBACK = {
    "rounds": [
        {"role": "bear", "label": "Bear Analyst", "text": "Macro and geopolitical risk signals are elevated for this ticker. Revenue concentration and regulatory exposure create a meaningful downside scenario under stress conditions.", "score": 7.5},
        {"role": "bull", "label": "Bull Analyst", "text": "The company's competitive moat and diversified demand base provide resilience. Non-affected segments can absorb near-term pressure while the risk scenario plays out.", "score": 6.5},
        {"role": "judge", "label": "Black Swan Judge", "text": "The tribunal recommends a moderate hedge position. Apply a revenue haircut and WACC premium until the risk scenario resolves. RECOMMENDATION — HEDGE: reduce exposure by 20-30% pending clarity.", "score": 8.5},
    ],
    "proposed_assumptions": {"revenue_haircut_pct": 20.0, "margin_compression_bps": 300, "wacc_premium_bps": 280, "terminal_growth_delta": -1.0},
    "bear_score": 7.5,
    "bull_score": 6.5,
}


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, default=str).encode("utf-8")
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


def handle(payload: dict[str, Any]) -> dict:
    return run_tribunal(
        ticker=str(payload.get("ticker") or "NVDA"),
        incident=str(payload.get("incident") or payload.get("description") or "Unspecified crisis incident"),
        chaos_index=float(payload.get("chaos_index") or 0.5),
        severity=str(payload.get("severity") or "watch"),
    )


def _fallback_payload(ticker: str = "NVDA") -> dict:
    try:
        return _fallback(str(ticker or "NVDA").upper())
    except Exception:
        return dict(_STATIC_FALLBACK)


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
        result = None
        payload: dict[str, Any] = {}
        try:
            payload = _read_json(self)
            result = handle(payload)
        except Exception as exc:
            traceback.print_exc()

        if result is None:
            # Try ticker-specific static fallback
            try:
                ticker = str(payload.get("ticker") or "NVDA").upper()
                result = _fallback_payload(ticker)
            except Exception:
                pass

        if result is None:
            result = dict(_STATIC_FALLBACK)

        _json_response(self, result, 200)
