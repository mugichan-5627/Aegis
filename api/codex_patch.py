from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    return json.loads(raw or "{}")


def _task_id() -> str:
    return f"AEGIS_PATCH_{datetime.now(timezone.utc).strftime('%Y%m%d')}_001"


def _codex_task(ticker: str, trigger_event: str, assumptions: dict) -> str:
    return f"""# Aegis_Codex Stress Module Patch

## Objective
Add a dedicated export-control stress scenario for {ticker.upper()} triggered by `{trigger_event}`.

## Required Model Changes
- Add an `ExportControlScenario` dataclass with jurisdiction exposure, compliance timeline, and substitution assumptions.
- Apply revenue haircut, EBITDA margin compression, WACC premium, and terminal-growth delta from the approved tribunal assumptions.
- Preserve human approval before any generated patch is merged.

## Approved Assumptions
- Revenue haircut: {assumptions.get('revenue_haircut_pct', assumptions.get('china_revenue_exposure', 28.5))}%
- Margin compression: {assumptions.get('margin_compression_bps', 420)} bps
- WACC premium: {assumptions.get('wacc_premium_bps', 380)} bps
- Terminal growth delta: {assumptions.get('terminal_growth_delta', -1.4)}%

## Tests Required
- `test_export_control_{ticker.lower()}_baseline`
- `test_wacc_regulatory_premium`
- `test_regression_{ticker.lower()}_golden`
"""


def _scenario_patch(ticker: str, trigger_event: str, assumptions: dict) -> dict:
    return {
        "scenario_id": f"export_ctrl_{ticker.lower()}_2026",
        "trigger_event": trigger_event,
        "affected_tickers": [ticker.upper()],
        "assumptions": {
            **assumptions,
            "compliance_scenarios": {
                "immediate": {
                    "haircut": float(assumptions.get("china_revenue_exposure", 0.385)),
                    "wacc_delta_bps": int(assumptions.get("wacc_premium_bps", 380)),
                    "terminal_growth_delta": float(assumptions.get("terminal_growth_delta", -1.4)),
                },
                "partial": {
                    "haircut": round(float(assumptions.get("china_revenue_exposure", 0.385)) * 0.47, 3),
                    "wacc_delta_bps": 180,
                    "terminal_growth_delta": -0.6,
                },
                "adaptation": {
                    "haircut": round(float(assumptions.get("china_revenue_exposure", 0.385)) * 0.18, 3),
                    "wacc_delta_bps": 80,
                    "terminal_growth_delta": -0.2,
                },
            },
        },
        "human_approval_required": True,
    }


def _generate_patch_code(ticker: str, trigger_event: str, assumptions: dict) -> str | None:
    key = os.environ.get("OPENAI_API_KEY", None)
    if not key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Python code generator. Return only valid Python code, no markdown fences.",
                },
                {
                    "role": "user",
                    "content": (
                        "Generate a concise Python subclass/dataclass stub for an export-control "
                        f"stress module for {ticker} triggered by {trigger_event}. "
                        f"Use these assumptions: {json.dumps(assumptions)}"
                    ),
                },
            ],
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception:
        return None


def handle(payload: dict[str, Any]) -> dict:
    ticker = str(payload.get("ticker") or "NVDA").upper()
    trigger_event = str(payload.get("trigger_event") or "EAR_99_CHINA_GPU_EXPANSION")
    assumptions = payload.get("assumptions") if isinstance(payload.get("assumptions"), dict) else {}
    if not assumptions:
        assumptions = {
            "china_revenue_exposure": 0.385,
            "compliance_timeline_months": 12,
            "revenue_haircut_pct": 28.5,
            "margin_compression_bps": 420,
            "wacc_premium_bps": 380,
            "terminal_growth_delta": -1.4,
        }

    return {
        "task_id": _task_id(),
        "codex_task": _codex_task(ticker, trigger_event, assumptions),
        "scenario_patch": _scenario_patch(ticker, trigger_event, assumptions),
        "patch_code": _generate_patch_code(ticker, trigger_event, assumptions),
        "human_approval_required": True,
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        _json_response(self, {"ok": True})

    def do_POST(self) -> None:
        try:
            _json_response(self, handle(_read_json(self)))
        except Exception:
            _json_response(self, handle({}), 200)
