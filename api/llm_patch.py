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
    body = json.dumps(payload, default=str).encode("utf-8")
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


def _llm_task(ticker: str, trigger_event: str, assumptions: dict) -> str:
    return f"""# Aegis Stress Module Patch

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


def _generate_patch_code(ticker: str, trigger_event: str, assumptions: dict) -> str:
    """Generate Python patch stub — tries primary model first, falls back to Nvidia NIM."""
    prompt = (
        "Generate a concise Python dataclass and function stub for a stress scenario module "
        f"for ticker {ticker} triggered by {trigger_event}. "
        "Include: a dataclass with revenue_haircut_pct, wacc_premium_bps, compliance_timeline_months fields; "
        "a function apply_stress(base_valuation, scenario) that applies the haircut and WACC delta; "
        "and 3 pytest function stubs. Return only valid Python, no markdown fences. "
        f"Use these approved assumptions: {json.dumps(assumptions)}"
    )

    # Try OpenAI first
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a Python code generator. Return only valid Python code, no markdown fences."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
            )
            code = response.choices[0].message.content
            if code and code.strip():
                return code
        except Exception:
            pass

    # Fallback to Nvidia NIM
    nvidia_key = os.environ.get("NVIDIA_API_KEY")
    if nvidia_key:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=nvidia_key,
                base_url="https://integrate.api.nvidia.com/v1",
            )
            response = client.chat.completions.create(
                model="meta/llama-3.3-70b-instruct",
                messages=[
                    {"role": "system", "content": "You are a Python code generator. Return only valid Python code, no markdown fences."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.2,
            )
            code = response.choices[0].message.content
            if code and code.strip():
                return f"# Generated via Nvidia NIM\n{code}"
        except Exception:
            pass

    # Static stub if both APIs unavailable
    t = ticker.upper()
    tl = ticker.lower()
    return f"""# Generated stub — connect NVIDIA_API_KEY or OPENAI_API_KEY for AI-generated code
from dataclasses import dataclass, field

@dataclass
class {t}StressScenario:
    revenue_haircut_pct: float = {assumptions.get('revenue_haircut_pct', 28.5)}
    wacc_premium_bps: int = {assumptions.get('wacc_premium_bps', 380)}
    compliance_timeline_months: int = {assumptions.get('compliance_timeline_months', 12)}
    margin_compression_bps: int = {assumptions.get('margin_compression_bps', 420)}

def apply_stress(base_valuation, scenario: {t}StressScenario):
    base_valuation.revenue *= (1 - scenario.revenue_haircut_pct / 100)
    base_valuation.wacc += scenario.wacc_premium_bps / 10000
    base_valuation.ebitda_margin -= scenario.margin_compression_bps / 10000
    return base_valuation

def test_stress_{tl}_baseline():
    pass  # TODO: assert revenue haircut applied correctly

def test_wacc_regulatory_premium():
    pass  # TODO: assert WACC delta = +{assumptions.get('wacc_premium_bps', 380)}bps

def test_regression_{tl}_golden():
    pass  # TODO: assert output within ±5% of golden snapshot
"""


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
        "llm_task": _llm_task(ticker, trigger_event, assumptions),
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
