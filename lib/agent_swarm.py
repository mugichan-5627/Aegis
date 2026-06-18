"""Serverless adversarial tribunal for Aegis_Codex."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from lib.local_telemetry import GLOBAL_TRACE_CONSOLE, arize_client


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
# Fast model keeps the tribunal reliably inside the serverless budget while
# Tavily grounding (below) supplies the company-specific richness.
NVIDIA_MODEL = "meta/llama-3.1-8b-instruct"
# Generous headroom so a slow-but-valid NIM response still lands instead of
# dropping to the generic fallback. Stays under the 30s function budget once
# Tavily (~2-3s) and overhead are added; the frontend waits 29s.
LLM_TIMEOUT_SECONDS = 24.0

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


def _fallback(ticker: str, incident: str = "", severity: str = "") -> dict:
    normalized_ticker = (ticker or "NVDA").upper()
    data = FALLBACK_DEBATES.get(normalized_ticker)
    if data:
        rounds = [dict(item) for item in data["rounds"]]
        assumptions = dict(data["proposed_assumptions"])
    else:
        assumptions = dict(DEFAULT_ASSUMPTIONS)
        # Weave the live incident in so even the no-LLM path references the real
        # company, sector and price move rather than pure boilerplate.
        profile = _company_context(normalized_ticker)
        profile_line = ""
        if profile:
            compact = "; ".join(
                line.replace("- ", "", 1)
                for line in profile.splitlines()[:5]
                if line.strip()
            )
            profile_line = f" Profile: {compact}."
        ctx = f" Trigger: {incident.strip()}" if incident else ""
        sev = (severity or "stress").lower()
        rounds = [
            {
                "role": "bear",
                "label": "Bear Analyst",
                "text": f"{normalized_ticker} is flagged as a {sev}-level case.{ctx}{profile_line} The bear view treats the live signal as a genuine repricing risk for this company's exposed revenue base before management can prove mitigation. Apply a revenue haircut, EBITDA margin compression and a higher risk premium until the signal cools.",
                "score": 7.4,
            },
            {
                "role": "bull",
                "label": "Bull Analyst",
                "text": f"{normalized_ticker} retains offsetting strengths that can limit permanent impairment.{profile_line} The bull view focuses on pricing power, balance-sheet flexibility and demand rotation across the company's actual business mix rather than assuming the headline shock flows one-for-one into intrinsic value. The case warrants monitoring, but the full bear scenario should not be treated as inevitable without confirming evidence.",
                "score": 6.3,
            },
            {
                "role": "judge",
                "label": "Black Swan Judge",
                "text": f"The tribunal assigns {normalized_ticker} a balanced but cautious {sev} verdict.{profile_line} The bear case wins on timing risk while the bull case matters for medium-term recovery through the company's own demand drivers and competitive position. RECOMMENDATION - HEDGE or reduce exposure modestly until live indicators improve, then re-run valuation with the approved stress assumptions.",
                "score": 8.4,
            },
        ]
    return {
        "rounds": rounds,
        "proposed_assumptions": assumptions,
        "bear_score": float(rounds[0]["score"]),
        "bull_score": float(rounds[1]["score"]),
    }


def _news_context(ticker: str, incident: str) -> str:
    """Pull recent, real headlines via Tavily so the tribunal can argue from
    company-specific facts (segments, customers, geographies, figures) instead
    of generic boilerplate. Returns a formatted bullet list, or "" if Tavily is
    unavailable."""
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return ""
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=key)
        query = (
            f"{ticker} stock news risk earnings guidance regulation competition "
            f"{incident}"
        )[:380]
        result = client.search(query=query, max_results=5, search_depth="basic")
        items = result.get("results") if isinstance(result, dict) else None
        if not items:
            return ""
        lines = []
        for it in items[:5]:
            if not isinstance(it, dict):
                continue
            title = str(it.get("title") or "").strip()
            body = str(it.get("content") or it.get("snippet") or "").strip()
            if title or body:
                lines.append(f"- {title}: {body[:170]}")
        # Keep the grounding compact so generation stays fast and reliable.
        return "\n".join(lines)[:1400]
    except Exception:
        return ""


def _company_context(ticker: str) -> str:
    """Fetch a compact company profile for ticker-specific grounding."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        fields = {
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "market_cap": info.get("marketCap"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "revenue_growth": info.get("revenueGrowth"),
            "ebitda_margin": info.get("ebitdaMargins"),
            "forward_pe": info.get("forwardPE"),
            "beta": info.get("beta"),
        }
        lines = []
        for key, value in fields.items():
            if value is None or value == "":
                continue
            if key == "market_cap":
                try:
                    value = f"${float(value) / 1_000_000_000:.1f}B"
                except Exception:
                    pass
            elif key in {"revenue_growth", "ebitda_margin"}:
                try:
                    value = f"{float(value) * 100:.1f}%"
                except Exception:
                    pass
            lines.append(f"- {key.replace('_', ' ')}: {value}")

        summary = str(info.get("longBusinessSummary") or "").strip()
        if summary:
            lines.append(f"- business summary: {summary[:520]}")
        return "\n".join(lines)[:1400]
    except Exception:
        return ""


def _client_and_model() -> tuple[OpenAI | None, str | None]:
    openai_key = os.environ.get("OPENAI_API_KEY", None)
    if openai_key:
        return OpenAI(api_key=openai_key, timeout=LLM_TIMEOUT_SECONDS, max_retries=0), "gpt-4o"

    nvidia_key = os.environ.get("NVIDIA_API_KEY", None)
    if nvidia_key:
        return OpenAI(
            api_key=nvidia_key,
            base_url=NVIDIA_BASE_URL,
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=0,
        ), NVIDIA_MODEL

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
        if len(text.split()) < 22 or ticker.upper() not in text.upper():
            text = fallback["rounds"][idx]["text"]
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
        fallback_res = _fallback(ticker, incident, severity)
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
        matching_trace = None
        for t in GLOBAL_TRACE_CONSOLE:
            if t["trace_id"] == trace_id:
                matching_trace = t.copy()
                matching_trace["endpoint"] = arize_client.endpoint_url
                break
        fallback_res["telemetry"] = matching_trace
        return fallback_res

    # Ground the debate in real, current headlines (logged as its own span).
    news_span = arize_client.start_span(trace_id=trace_id, name="Tavily News Retrieval")
    news = _news_context(ticker, incident)
    profile = _company_context(ticker)
    arize_client.complete_span(
        trace_id=trace_id,
        span_id=news_span["span_id"],
        inputs={"ticker": ticker, "incident": incident},
        outputs={"headlines": news[:1000] if news else "(none — Tavily unavailable)"},
        status="SUCCESS" if news else "SKIPPED",
    )
    profile_block = (
        "\nCOMPANY PROFILE (use these specifics before broad market language):\n"
        f"{profile}\n"
        if profile
        else ""
    )
    news_block = (
        "\nLIVE NEWS CONTEXT (cite specific facts, figures, products, customers, "
        "geographies and events from these — do NOT write generic statements that "
        f"could apply to any company):\n{news}\n"
        if news
        else ""
    )

    prompt = f"""You are running an adversarial investment tribunal on {ticker}.
{profile_block}{news_block}
Incident under review: {incident}
Chaos index: {chaos_index} (0-1 scale). Severity: {severity}.

Write three rounds of argument that are SPECIFIC to {ticker}. Reference the
company's actual business model, sector/industry, products or services, major
customers or demand drivers, competitors, geography, valuation pressure and
balance-sheet/risk profile where available. Where the profile or news context
gives concrete facts or numbers, use them. Every round must name {ticker} and
include at least two concrete company-specific facts. Avoid boilerplate that
could describe any company.

Return ONLY valid JSON (no markdown) matching this schema:
{{
  "rounds": [
    {{"role":"bear","label":"Bear Analyst","text":"4-5 sentences: specific downside thesis with concrete, named drivers","score":7.8}},
    {{"role":"bull","label":"Bull Analyst","text":"4-5 sentences: specific rebuttal naming real offsetting strengths","score":6.4}},
    {{"role":"judge","label":"Black Swan Judge","text":"4-5 sentences synthesis ending with 'RECOMMENDATION - HEDGE/HOLD/REDUCE ...'","score":9.1}}
  ],
  "proposed_assumptions": {{
    "revenue_haircut_pct": <number 0-60>,
    "margin_compression_bps": <integer 0-800>,
    "wacc_premium_bps": <integer 0-700>,
    "terminal_growth_delta": <negative number, e.g. -0.5 to -3.0>
  }}
}}

Scores are 0-10 conviction levels. CHOOSE proposed_assumptions values that are
justified by THIS company's specific risk, the incident, the severity
({severity}) and the chaos index ({chaos_index}) — do NOT copy the placeholder
ranges, and do not reuse round numbers like 28.5 / 420 / 380 unless they
genuinely fit. A higher chaos index means a deeper haircut and wider premium.
"""

    # Start a span for the LLM Swarm call
    llm_span = arize_client.start_span(trace_id=trace_id, name=f"LLM Swarm Synthesis ({model})")

    try:
        create_kwargs = dict(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are Aegis_Codex, an institutional crisis-valuation tribunal. You ground every argument in the specific company's fundamentals and the live news provided, never generic boilerplate. Return strict JSON only, no markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            max_tokens=900,
            timeout=LLM_TIMEOUT_SECONDS,
        )
        try:
            # JSON mode forces parseable output — the 8B model otherwise returns
            # slightly-off JSON intermittently, which dropped us to the generic
            # fallback. Retry without it if a model/endpoint rejects the param.
            response = client.chat.completions.create(
                response_format={"type": "json_object"}, **create_kwargs
            )
        except Exception:
            response = client.chat.completions.create(**create_kwargs)
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
            
            fallback_res = _fallback(ticker, incident, severity)
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
        
        matching_trace = None
        for t in GLOBAL_TRACE_CONSOLE:
            if t["trace_id"] == trace_id:
                # Deep-copy only serializable fields to avoid circular refs in spans
                matching_trace = {
                    "trace_id": t["trace_id"],
                    "name": t["name"],
                    "ticker": t.get("ticker", ""),
                    "start_time": t.get("start_time", ""),
                    "end_time": t.get("end_time", ""),
                    "duration_ms": t.get("duration_ms", 0),
                    "status": t.get("status", ""),
                    "endpoint": arize_client.endpoint_url,
                    "spans": [
                        {
                            "span_id": s.get("span_id", ""),
                            "name": s.get("name", ""),
                            "duration_ms": s.get("duration_ms", 0),
                            "status": s.get("status", ""),
                            "inputs": {k: str(v)[:200] for k, v in (s.get("inputs") or {}).items()},
                            "outputs": {k: str(v)[:200] for k, v in (s.get("outputs") or {}).items()},
                            "metadata": s.get("metadata") or {},
                        }
                        for s in t.get("spans", [])
                    ],
                }
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
        
        fallback_res = _fallback(ticker, incident, severity)
        matching_trace = None
        for t in GLOBAL_TRACE_CONSOLE:
            if t["trace_id"] == trace_id:
                matching_trace = t.copy()
                matching_trace["endpoint"] = arize_client.endpoint_url
                break
        fallback_res["telemetry"] = matching_trace
        return fallback_res
