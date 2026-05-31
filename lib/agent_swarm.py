"""Serverless adversarial tribunal for Aegis_Codex."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from arize_mcp_client import arize_client


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"

DEFAULT_ASSUMPTIONS = {
    "revenue_haircut_pct": 28.5,
    "margin_compression_bps": 420,
    "wacc_premium_bps": 380,
    "terminal_growth_delta": -1.4,
}

FALLBACK_DEBATES = {
    "NVDA": {
        "rounds": [
            {
                "role": "bear",
                "label": "Bear Analyst",
                "text": "NVDA faces a concentrated regulatory shock in its highest-growth datacenter corridor. A full China accelerator exit would remove near-term revenue before non-China hyperscaler demand can absorb the gap. Margin pressure follows because compliant SKUs carry redesign and channel costs while investors reprice regulatory durability.",
                "score": 7.8,
            },
            {
                "role": "bull",
                "label": "Bull Analyst",
                "text": "The Bear case underestimates NVIDIA's demand elasticity outside China. US hyperscalers, sovereign AI buyers, and enterprise inference demand remain supply-constrained, so lost China allocation can be redeployed over time. The company also has enough cash generation to fund compliance redesigns without balance-sheet stress.",
                "score": 6.4,
            },
            {
                "role": "judge",
                "label": "Black Swan Judge",
                "text": "The tribunal weights the Bear case higher because market pricing will punish the transition gap before substitution demand is visible. The Bull case is credible over 18-24 months, but the next two quarters carry material estimate risk. Use a revenue haircut, EBITDA margin compression, and regulatory WACC premium until export-control clarity improves.",
                "score": 9.1,
            },
        ],
        "proposed_assumptions": DEFAULT_ASSUMPTIONS,
    },
    "TSM": {
        "rounds": [
            {
                "role": "bear",
                "label": "Bear Analyst",
                "text": "TSM carries an unmatched physical concentration risk because leading-edge capacity remains anchored in Taiwan. A blockade scare or insurance withdrawal can impair customer planning even without a full kinetic event. The valuation must reflect disruption probability, logistics delays, and forced inventory premiums.",
                "score": 8.1,
            },
            {
                "role": "bull",
                "label": "Bull Analyst",
                "text": "TSMC is protected by its systemic importance to the global economy and by deep customer dependency. Arizona expansion and multinational deterrence reduce the probability of a terminal disruption. Its pricing power and technology lead remain strong enough to offset moderate geopolitical discounts.",
                "score": 6.7,
            },
            {
                "role": "judge",
                "label": "Black Swan Judge",
                "text": "The correct stance is partial stress, not existential collapse. Deterrence matters, but markets can still price a higher disruption premium when military signaling intensifies. Apply a meaningful WACC premium and a moderate revenue disruption haircut while preserving a strategic moat scenario.",
                "score": 8.8,
            },
        ],
        "proposed_assumptions": {
            "revenue_haircut_pct": 22.0,
            "margin_compression_bps": 330,
            "wacc_premium_bps": 420,
            "terminal_growth_delta": -1.2,
        },
    },
    "ASML": {
        "rounds": [
            {
                "role": "bear",
                "label": "Bear Analyst",
                "text": "ASML's export-license dependency is a single diplomatic choke point. If US-Dutch restrictions tighten, China shipment visibility falls and order timing becomes politically gated. EUV scarcity protects the franchise, but DUV and service exposure can still face a sharp revenue reset.",
                "score": 6.9,
            },
            {
                "role": "bull",
                "label": "Bull Analyst",
                "text": "ASML remains irreplaceable for advanced semiconductor manufacturing. Demand from TSMC, Samsung, Intel, and memory customers can absorb a large share of restricted China capacity. Regulatory pressure may even extend ASML's moat by slowing domestic Chinese tool competition.",
                "score": 7.1,
            },
            {
                "role": "judge",
                "label": "Black Swan Judge",
                "text": "ASML deserves an elevated but not critical stress classification. The risk is order timing and regional mix, not demand destruction for lithography as a category. Use a smaller revenue haircut with a moderate WACC premium until license renewal is settled.",
                "score": 8.0,
            },
        ],
        "proposed_assumptions": {
            "revenue_haircut_pct": 16.0,
            "margin_compression_bps": 240,
            "wacc_premium_bps": 260,
            "terminal_growth_delta": -0.8,
        },
    },
}


def _fallback(ticker: str) -> dict:
    data = FALLBACK_DEBATES.get(ticker.upper(), FALLBACK_DEBATES["NVDA"])
    rounds = [dict(item) for item in data["rounds"]]
    assumptions = dict(data["proposed_assumptions"])
    return {
        "rounds": rounds,
        "proposed_assumptions": assumptions,
        "bear_score": float(rounds[0]["score"]),
        "bull_score": float(rounds[1]["score"]),
    }


def _client_and_model() -> tuple[OpenAI | None, str | None]:
    openai_key = os.environ.get("OPENAI_API_KEY", None)
    if openai_key:
        return OpenAI(api_key=openai_key), "gpt-4o"

    nvidia_key = os.environ.get("NVIDIA_API_KEY", None)
    if nvidia_key:
        return OpenAI(api_key=nvidia_key, base_url=NVIDIA_BASE_URL), NVIDIA_MODEL

    return None, None


def _extract_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _normalize(payload: dict, ticker: str) -> dict:
    fallback = _fallback(ticker)
    rounds = payload.get("rounds") if isinstance(payload, dict) else None
    if not isinstance(rounds, list) or len(rounds) < 3:
        return fallback

    roles = [
        ("bear", "Bear Analyst"),
        ("bull", "Bull Analyst"),
        ("judge", "Black Swan Judge"),
    ]
    normalized = []
    for idx, (role, label) in enumerate(roles):
        item = rounds[idx] if isinstance(rounds[idx], dict) else {}
        text = str(item.get("text") or item.get("argument") or fallback["rounds"][idx]["text"])
        try:
            score = float(item.get("score", fallback["rounds"][idx]["score"]))
        except Exception:
            score = fallback["rounds"][idx]["score"]
        normalized.append(
            {
                "role": role,
                "label": label,
                "text": text[:1600],
                "score": round(max(0.0, min(10.0, score)), 1),
            }
        )

    assumptions = payload.get("proposed_assumptions") or fallback["proposed_assumptions"]
    clean_assumptions = {}
    for key, default in fallback["proposed_assumptions"].items():
        try:
            clean_assumptions[key] = round(float(assumptions.get(key, default)), 1)
        except Exception:
            clean_assumptions[key] = default

    return {
        "rounds": normalized,
        "proposed_assumptions": clean_assumptions,
        "bear_score": normalized[0]["score"],
        "bull_score": normalized[1]["score"],
    }


def run_tribunal(
    ticker: str,
    incident: str,
    chaos_index: float,
    severity: str,
) -> dict:
    """Run Bear/Bull/Judge tribunal with OpenAI, NVIDIA, or deterministic fallback."""
    ticker = (ticker or "NVDA").upper()
    
    # 1. Initialize parent trace
    trace = arize_client.create_trace(name=f"Tribunal Debate: {ticker}", ticker=ticker)
    trace_id = trace["trace_id"]
    
    client, model = _client_and_model()
    if not client or not model:
        fallback_res = _fallback(ticker)
        # Log spans for fallback execution
        for round_idx, r in enumerate(fallback_res["rounds"]):
            span_name = f"Swarm Segment: {r['label']}"
            span = arize_client.start_span(trace_id=trace_id, name=span_name)
            arize_client.complete_span(
                trace_id=trace_id,
                span_id=span["span_id"],
                inputs={"ticker": ticker, "incident": incident, "role": r["role"]},
                outputs={"text": r["text"], "score": r["score"]},
                status="SUCCESS",
                metadata={"execution": "fallback"}
            )
        arize_client.complete_trace(trace_id=trace_id)
        
        # Pull trace from local memory store
        from arize_mcp_client import GLOBAL_TRACE_CONSOLE
        matching_trace = None
        for t in GLOBAL_TRACE_CONSOLE:
            if t["trace_id"] == trace_id:
                matching_trace = t.copy()
                matching_trace["endpoint"] = arize_client.endpoint_url
                break
        fallback_res["telemetry"] = matching_trace
        return fallback_res

    prompt = f"""
Return only valid JSON matching this schema:
{{
  "rounds": [
    {{"role":"bear","label":"Bear Analyst","text":"3-5 sentences","score":7.8}},
    {{"role":"bull","label":"Bull Analyst","text":"3-5 sentences","score":6.4}},
    {{"role":"judge","label":"Black Swan Judge","text":"3-5 sentences","score":9.1}}
  ],
  "proposed_assumptions": {{
    "revenue_haircut_pct": 28.5,
    "margin_compression_bps": 420,
    "wacc_premium_bps": 380,
    "terminal_growth_delta": -1.4
  }}
}}

Ticker: {ticker}
Incident: {incident}
Chaos index: {chaos_index}
Severity: {severity}

Run exactly three rounds: Bear prosecution, Bull defense, and Black Swan Judge synthesis.
Keep each text under five sentences and make the assumptions numeric.
"""

    # Start a span for the LLM Swarm call
    llm_span = arize_client.start_span(trace_id=trace_id, name=f"LLM Swarm Synthesis ({model})")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are Aegis_Codex, an institutional crisis valuation tribunal. Return strict JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            max_tokens=900,
        )
        text = response.choices[0].message.content or ""
        parsed = _extract_json(text)
        if not parsed:
            arize_client.complete_span(
                trace_id=trace_id,
                span_id=llm_span["span_id"],
                inputs={"prompt": prompt},
                outputs={"raw_text": text},
                status="ERROR",
                metadata={"error": "JSON parse failure"}
            )
            arize_client.complete_trace(trace_id=trace_id)
            
            fallback_res = _fallback(ticker)
            from arize_mcp_client import GLOBAL_TRACE_CONSOLE
            matching_trace = None
            for t in GLOBAL_TRACE_CONSOLE:
                if t["trace_id"] == trace_id:
                    matching_trace = t
                    break
            fallback_res["telemetry"] = matching_trace
            return fallback_res
            
        normalized = _normalize(parsed, ticker)
        
        arize_client.complete_span(
            trace_id=trace_id,
            span_id=llm_span["span_id"],
            inputs={"prompt": prompt},
            outputs=normalized,
            status="SUCCESS"
        )
        
        # Log spans for each Swarm Advocate Role
        for round_idx, r in enumerate(normalized["rounds"]):
            span_name = f"Swarm Segment: {r['label']}"
            s_span = arize_client.start_span(trace_id=trace_id, name=span_name)
            arize_client.complete_span(
                trace_id=trace_id,
                span_id=s_span["span_id"],
                inputs={"ticker": ticker, "incident": incident, "role": r["role"]},
                outputs={"text": r["text"], "score": r["score"]},
                status="SUCCESS"
            )
            
        arize_client.complete_trace(trace_id=trace_id)
        
        from arize_mcp_client import GLOBAL_TRACE_CONSOLE
        matching_trace = None
        for t in GLOBAL_TRACE_CONSOLE:
            if t["trace_id"] == trace_id:
                matching_trace = t.copy()
                matching_trace["endpoint"] = arize_client.endpoint_url
                break
        normalized["telemetry"] = matching_trace
        return normalized
        
    except Exception as e:
        arize_client.complete_span(
            trace_id=trace_id,
            span_id=llm_span["span_id"],
            inputs={"prompt": prompt},
            outputs={},
            status="ERROR",
            metadata={"error": str(e)}
        )
        arize_client.complete_trace(trace_id=trace_id)
        
        fallback_res = _fallback(ticker)
        from arize_mcp_client import GLOBAL_TRACE_CONSOLE
        matching_trace = None
        for t in GLOBAL_TRACE_CONSOLE:
            if t["trace_id"] == trace_id:
                matching_trace = t.copy()
                matching_trace["endpoint"] = arize_client.endpoint_url
                break
        fallback_res["telemetry"] = matching_trace
        return fallback_res
