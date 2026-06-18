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


def _slug(value: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in text.split("_") if part)[:48] or "market_stress"


def _llm_task(
    ticker: str,
    trigger_event: str,
    assumptions: dict,
    incident: str = "",
    severity: str = "",
    chaos_index: float | None = None,
) -> str:
    risk_line = incident or trigger_event
    severity_line = f"{severity or 'watch'}"
    chaos_line = "n/a" if chaos_index is None else f"{chaos_index:.2f}"
    ticker_slug = _slug(ticker)
    return f"""# Aegis Stress Module Patch

## Objective
Add a dedicated stress scenario for {ticker.upper()} triggered by `{trigger_event}`.

## Live Incident Context
- Incident: {risk_line}
- Severity: {severity_line}
- Chaos index: {chaos_line}

## Required Model Changes
- Add a `{ticker.upper()}StressScenario` dataclass with event exposure, mitigation timeline, and substitution assumptions.
- Apply revenue haircut, EBITDA margin compression, WACC premium, and terminal-growth delta from the approved tribunal assumptions.
- Document why each assumption follows from the Bear/Bull/Judge debate and the live Watchtower signal.
- Preserve human approval before any generated patch is merged.

## Approved Assumptions
- Revenue haircut: {assumptions.get('revenue_haircut_pct', assumptions.get('china_revenue_exposure', 28.5))}%
- Margin compression: {assumptions.get('margin_compression_bps', 420)} bps
- WACC premium: {assumptions.get('wacc_premium_bps', 380)} bps
- Terminal growth delta: {assumptions.get('terminal_growth_delta', -1.4)}%

## Tests Required
- `test_stress_{ticker_slug}_baseline`
- `test_wacc_regulatory_premium`
- `test_regression_{ticker_slug}_golden`
"""


def _scenario_patch(
    ticker: str,
    trigger_event: str,
    assumptions: dict,
    incident: str = "",
    severity: str = "",
    chaos_index: float | None = None,
) -> dict:
    scenario_kind = _slug(trigger_event or incident)
    ticker_slug = _slug(ticker)
    exposure = float(assumptions.get("revenue_haircut_pct", 28.5)) / 100
    return {
        "scenario_id": f"{scenario_kind}_{ticker_slug}_2026",
        "trigger_event": trigger_event,
        "incident": incident,
        "severity": severity or "watch",
        "chaos_index": chaos_index,
        "affected_tickers": [ticker.upper()],
        "assumptions": {
            **assumptions,
            "stress_paths": {
                "immediate": {
                    "haircut": exposure,
                    "wacc_delta_bps": int(assumptions.get("wacc_premium_bps", 380)),
                    "terminal_growth_delta": float(assumptions.get("terminal_growth_delta", -1.4)),
                },
                "partial": {
                    "haircut": round(exposure * 0.55, 3),
                    "wacc_delta_bps": round(int(assumptions.get("wacc_premium_bps", 380)) * 0.55),
                    "terminal_growth_delta": -0.6,
                },
                "adaptation": {
                    "haircut": round(exposure * 0.22, 3),
                    "wacc_delta_bps": round(int(assumptions.get("wacc_premium_bps", 380)) * 0.25),
                    "terminal_growth_delta": -0.2,
                },
            },
        },
        "human_approval_required": True,
    }


def _strip_code_fences(code: str) -> str:
    """Remove leading/trailing markdown code fences (```python ... ```) that LLMs
    add despite instructions, so the preview shows clean Python only."""
    text = (code or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop the opening fence (``` or ```python)
        lines = lines[1:]
        # drop the closing fence if present
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _looks_like_patch_code(code: str) -> bool:
    text = code or ""
    return "@dataclass" in text and "def apply_stress" in text and "def test_" in text


def _static_patch_code(ticker: str, assumptions: dict) -> str:
    class_name = "".join(part.capitalize() for part in _slug(ticker).split("_")) or "Ticker"
    tl = _slug(ticker)
    return f"""# Generated stub - connect NVIDIA_API_KEY or OPENAI_API_KEY for AI-generated code
from dataclasses import dataclass

@dataclass
class {class_name}StressScenario:
    revenue_haircut_pct: float = {assumptions.get('revenue_haircut_pct', 28.5)}
    wacc_premium_bps: int = {assumptions.get('wacc_premium_bps', 380)}
    mitigation_timeline_months: int = {assumptions.get('compliance_timeline_months', 12)}
    margin_compression_bps: int = {assumptions.get('margin_compression_bps', 420)}

def apply_stress(base_valuation, scenario: {class_name}StressScenario):
    base_valuation.revenue *= (1 - scenario.revenue_haircut_pct / 100)
    base_valuation.wacc += scenario.wacc_premium_bps / 10000
    base_valuation.ebitda_margin -= scenario.margin_compression_bps / 10000
    return base_valuation

def test_stress_{tl}_baseline():
    pass  # TODO: assert revenue haircut applied correctly

def test_wacc_regulatory_premium():
    pass  # TODO: assert WACC delta = +{assumptions.get('wacc_premium_bps', 380)}bps

def test_regression_{tl}_golden():
    pass  # TODO: assert output within +/-5% of golden snapshot
"""


def _generate_patch_code(
    ticker: str,
    trigger_event: str,
    assumptions: dict,
    incident: str = "",
    severity: str = "",
    chaos_index: float | None = None,
) -> str:
    """Generate Python patch stub — tries primary model first, falls back to Nvidia NIM."""
    prompt = (
        "Generate a concise Python dataclass and function stub for a stress scenario module "
        f"for ticker {ticker} triggered by {trigger_event}. "
        f"Incident: {incident or trigger_event}. Severity: {severity or 'watch'}. Chaos index: {chaos_index}. "
        "Include: a dataclass with revenue_haircut_pct, wacc_premium_bps, mitigation_timeline_months fields; "
        "a function apply_stress(base_valuation, scenario) that applies the haircut and WACC delta; "
        "and 3 pytest function stubs. Return only valid Python, no markdown fences. "
        f"Use these approved assumptions: {json.dumps(assumptions)}"
    )

    # Try OpenAI first
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key, timeout=20.0, max_retries=0)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a Python code generator. Return only valid Python code, no markdown fences."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=380,
            )
            code = _strip_code_fences(response.choices[0].message.content or "")
            if _looks_like_patch_code(code):
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
                timeout=18.0,
                max_retries=0,
            )
            # Use the fast 8B model for interactive patch generation: it returns real
            # LLM output in ~5-8s, reliably inside the serverless budget. (The 70B model
            # powers the Tribunal debate, where latency is less critical.)
            response = client.chat.completions.create(
                model="meta/llama-3.1-8b-instruct",
                messages=[
                    {"role": "system", "content": "You are a Python code generator. Return only valid Python code, no markdown fences."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=380,
                temperature=0.2,
            )
            code = _strip_code_fences(response.choices[0].message.content or "")
            if _looks_like_patch_code(code):
                return f"# Generated via Nvidia NIM\n{code}"
        except Exception:
            pass

    # Static stub if both APIs unavailable or model output fails validation.
    return _static_patch_code(ticker, assumptions)


def handle(payload: dict[str, Any]) -> dict:
    ticker = str(payload.get("ticker") or "NVDA").upper()
    trigger_event = str(payload.get("trigger_event") or "WATCHTOWER_STRESS_EVENT")
    incident = str(payload.get("incident") or payload.get("description") or "")
    severity = str(payload.get("severity") or "")
    try:
        chaos_index = float(payload.get("chaos_index")) if payload.get("chaos_index") is not None else None
    except Exception:
        chaos_index = None
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
        "llm_task": _llm_task(ticker, trigger_event, assumptions, incident, severity, chaos_index),
        "scenario_patch": _scenario_patch(ticker, trigger_event, assumptions, incident, severity, chaos_index),
        "patch_code": _generate_patch_code(ticker, trigger_event, assumptions, incident, severity, chaos_index),
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
