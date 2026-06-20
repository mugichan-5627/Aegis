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
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
NVIDIA_QUALITY_MODEL = os.environ.get("NVIDIA_QUALITY_MODEL")
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

CURATED_COMPANY_PROFILES = {
    "AVGO": {
        "name": "Broadcom Inc.",
        "sector": "Technology",
        "industry": "Semiconductors",
        "business_model": "AI networking silicon, custom accelerators, merchant switching, broadband/wireless chips, and infrastructure software after VMware.",
        "demand_drivers": "Hyperscaler AI cluster spending, Ethernet switching upgrades, custom ASIC ramps, VMware subscription conversion, and enterprise infrastructure budgets.",
        "key_risks": "Hyperscaler order concentration, AI networking digestion, VMware integration execution, China/export exposure, and high expectations embedded in AI semiconductor multiples.",
        "peers": "NVIDIA, Marvell, AMD, Cisco, Arista, Qualcomm, Oracle infrastructure software.",
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "business_model": "Azure cloud, Office/Microsoft 365, Windows, LinkedIn, Dynamics, gaming, security, and AI copilots.",
        "demand_drivers": "Azure consumption, AI infrastructure utilization, Copilot attach rates, enterprise renewals, and operating leverage in commercial cloud.",
        "key_risks": "AI capex monetization lag, cloud growth deceleration, regulatory scrutiny, OpenAI dependency, and enterprise software budget pressure.",
        "peers": "Amazon AWS, Google Cloud, Oracle Cloud, Salesforce, Adobe.",
    },
    "JPM": {
        "name": "JPMorgan Chase & Co.",
        "sector": "Financial Services",
        "industry": "Banks - Diversified",
        "business_model": "Consumer banking, commercial banking, investment banking, markets, payments, asset and wealth management.",
        "demand_drivers": "Net interest income, credit quality, loan growth, trading volatility, investment banking fees, and deposit beta.",
        "key_risks": "Credit cycle deterioration, deposit repricing, capital rules, commercial real estate exposure, and lower rate sensitivity.",
        "peers": "Bank of America, Citi, Wells Fargo, Goldman Sachs, Morgan Stanley.",
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors",
        "business_model": "Data-center GPUs, networking, CUDA software ecosystem, gaming GPUs, professional visualization, and automotive AI.",
        "demand_drivers": "Hyperscaler AI training/inference capex, Blackwell/Hopper supply, networking attach, sovereign AI, and CUDA platform lock-in.",
        "key_risks": "Export controls, hyperscaler digestion, custom ASIC substitution, gross-margin normalization, and extreme valuation expectations.",
        "peers": "AMD, Broadcom, Marvell, Intel, custom silicon from Google/Amazon/Microsoft.",
    },
    "TSM": {
        "name": "Taiwan Semiconductor Manufacturing Company",
        "sector": "Technology",
        "industry": "Semiconductors",
        "business_model": "Pure-play foundry manufacturing for leading-edge and specialty semiconductor customers.",
        "demand_drivers": "Advanced-node wafer demand, AI accelerator ramps, Apple/mobile cycles, HPC demand, and pricing power at 3nm/2nm.",
        "key_risks": "Taiwan geopolitical risk, customer concentration, capex intensity, power/water constraints, and cyclicality in non-AI semis.",
        "peers": "Samsung Foundry, Intel Foundry, GlobalFoundries, UMC, SMIC.",
    },
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
        profile = _company_profile(normalized_ticker)
        name = profile.get("name") or normalized_ticker
        industry = profile.get("industry") or profile.get("sector") or "its sector"
        business = _clean_fragment(profile.get("business_model") or profile.get("summary") or "its operating model")
        demand = _clean_fragment(profile.get("demand_drivers") or "the next demand cycle")
        risks = _clean_fragment(profile.get("key_risks") or "estimate risk, cost pressure and multiple compression")
        peers = _clean_fragment(profile.get("peers") or "direct competitors")
        ctx = f" Trigger: {incident.strip()}" if incident else ""
        sev = (severity or "stress").lower()
        rounds = [
            {
                "role": "bear",
                "label": "Bear Analyst",
                "text": f"{normalized_ticker} ({name}) is flagged as a {sev}-level case in {industry}.{ctx} The bear case starts from its actual business mix: {business}. If the live signal persists, investors can mark down {demand} before management proves resilience; the exposed pressure points are {risks}. Relative to {peers}, the stock deserves a revenue haircut, margin compression and a higher risk premium until order activity, guidance or market action confirms the shock is fading.",
                "score": 7.4,
            },
            {
                "role": "bull",
                "label": "Bull Analyst",
                "text": f"{normalized_ticker}'s bull case is not a generic balance-sheet argument; it rests on the durability of {business}. The same drivers the bear case worries about, especially {demand}, can also absorb a temporary macro or supply-chain scare if customer demand remains intact. Against {peers}, the question is whether the incident changes normalized earnings power or only near-term positioning. Without confirming evidence of lost share, cancelled orders or structural margin damage, the full bear haircut should stay probabilistic rather than automatic.",
                "score": 6.3,
            },
            {
                "role": "judge",
                "label": "Black Swan Judge",
                "text": f"The tribunal assigns {normalized_ticker} a balanced but cautious {sev} verdict because the incident is hitting a business where {business}. The Bear case wins the next-quarter timing argument through {risks}, while the Bull case depends on {demand} staying healthy versus {peers}. The right action is to stress valuation assumptions now, then update them when fresh guidance, order commentary or price action confirms whether this is cyclic noise or a real expectation reset. RECOMMENDATION - HEDGE or reduce exposure modestly until live indicators improve, then re-run valuation with the approved stress assumptions.",
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


def _company_profile(ticker: str) -> dict:
    """Return a compact, structured company profile for tribunal grounding."""
    normalized = (ticker or "").upper()
    profile = dict(CURATED_COMPANY_PROFILES.get(normalized, {}))
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        for key, value in {
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
            "summary": info.get("longBusinessSummary"),
        }.items():
            if value is not None and value != "" and not profile.get(key):
                profile[key] = value
    except Exception:
        pass
    return profile


def _format_company_context(profile: dict) -> str:
    lines = []
    for key in (
        "name",
        "sector",
        "industry",
        "country",
        "market_cap",
        "current_price",
        "revenue_growth",
        "ebitda_margin",
        "forward_pe",
        "beta",
        "business_model",
        "demand_drivers",
        "key_risks",
        "peers",
        "summary",
    ):
        value = profile.get(key)
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
        text = str(value).strip()
        if key == "summary":
            text = text[:520]
        lines.append(f"- {key.replace('_', ' ')}: {text}")
    return "\n".join(lines)[:1800]


def _clean_fragment(value: Any) -> str:
    return str(value or "").strip().rstrip(".")


def _company_context(ticker: str) -> str:
    """Fetch a compact company profile for ticker-specific grounding."""
    try:
        return _format_company_context(_company_profile(ticker))
    except Exception:
        return ""


def _specificity_score(text: str, ticker: str, profile: dict) -> int:
    haystack = (text or "").lower()
    score = 0
    if ticker.lower() in haystack:
        score += 1
    for key in ("name", "industry", "business_model", "demand_drivers", "key_risks", "peers"):
        value = str(profile.get(key) or "")
        for token in re.findall(r"[A-Za-z][A-Za-z0-9&.-]{3,}", value):
            if token.lower() in haystack:
                score += 1
                break
    banned = ("large liquid", "pricing power", "balance-sheet flexibility", "business mix", "headline shock")
    if any(phrase in haystack for phrase in banned):
        score -= 1
    return score


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


def _model_candidates(primary: str | None) -> list[str]:
    if not primary:
        return []
    candidates = []
    if NVIDIA_QUALITY_MODEL:
        candidates.append(NVIDIA_QUALITY_MODEL)
    candidates.append(primary)
    if primary != "meta/llama-3.1-8b-instruct":
        candidates.append("meta/llama-3.1-8b-instruct")
    return list(dict.fromkeys(candidates))


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


def _run_llm_candidates(client: OpenAI, candidates: list[str], prompt: str) -> tuple[dict | None, str, str | None, list[str]]:
    parsed = None
    text = ""
    selected_model = candidates[0] if candidates else None
    errors: list[str] = []
    for candidate in candidates:
        create_kwargs = dict(
            model=candidate,
            messages=[
                {
                    "role": "system",
                    "content": "You are Aegis_Codex, an institutional crisis-valuation tribunal. You ground every argument in the specific company's core business, current environment, live news, recent market activity and forward expectations. Return strict JSON only, no markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.28,
            max_tokens=1200,
            timeout=LLM_TIMEOUT_SECONDS,
        )
        try:
            try:
                response = client.chat.completions.create(
                    response_format={"type": "json_object"}, **create_kwargs
                )
            except Exception:
                response = client.chat.completions.create(**create_kwargs)
            text = response.choices[0].message.content or ""
            parsed = _extract_json(text)
            if parsed:
                selected_model = candidate
                break
            errors.append(f"{candidate}: JSON parse failure")
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")
    return parsed, text, selected_model, errors


def _normalize(
    payload: dict,
    ticker: str,
    profile: dict | None = None,
    incident: str = "",
    severity: str = "",
) -> dict:
    fallback = _fallback(ticker, incident, severity)
    profile = profile or _company_profile(ticker)
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
        min_specificity = 2 if any(profile.get(k) for k in ("business_model", "demand_drivers", "key_risks")) else 1
        if len(text.split()) < 45 or _specificity_score(text, ticker, profile) < min_specificity:
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
    profile = _company_profile(ticker)
    profile_text = _format_company_context(profile)
    arize_client.complete_span(
        trace_id=trace_id,
        span_id=news_span["span_id"],
        inputs={"ticker": ticker, "incident": incident},
        outputs={"headlines": news[:1000] if news else "(none — Tavily unavailable)"},
        status="SUCCESS" if news else "SKIPPED",
    )
    profile_block = (
        "\nCOMPANY PROFILE (use these specifics before broad market language):\n"
        f"{profile_text}\n"
        if profile_text
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

Think like a senior public-equity analyst before writing. For each role, reason
through this chain explicitly: (1) what {ticker} actually sells, (2) which
revenue/margin driver the incident touches, (3) how current headlines or market
activity change forward expectations over the next 1-4 quarters, (4) what
evidence would confirm or falsify the thesis, and (5) the valuation implication.

Every round must name {ticker} and include at least three concrete facts from
the company profile, business model, demand drivers, risk list, peers, news
context, recent market move, chaos index or severity. Do not use generic phrases
like "large liquid franchise", "pricing power", "business mix", or "balance
sheet flexibility" unless tied to a named segment, product, customer base,
margin driver or peer comparison.

Return ONLY valid JSON (no markdown) matching this schema:
{{
  "rounds": [
    {{"role":"bear","label":"Bear Analyst","text":"5-7 sentences: company-specific downside thesis; name affected segment/product/demand driver, forward-estimate impact, market signal and evidence to watch","score":7.8}},
    {{"role":"bull","label":"Bull Analyst","text":"5-7 sentences: company-specific rebuttal; name durable segment/product/demand driver, why the incident may not impair normalized earnings, peer/customer context and evidence to watch","score":6.4}},
    {{"role":"judge","label":"Black Swan Judge","text":"5-7 sentences: synthesis; explain which thesis wins, why, what assumption changes follow, what data would change the verdict, ending with 'RECOMMENDATION - HEDGE/HOLD/REDUCE ...'","score":9.1}}
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

    model_candidates = _model_candidates(model)
    # Start a span for the LLM Swarm call
    llm_span = arize_client.start_span(trace_id=trace_id, name=f"LLM Swarm Synthesis ({' -> '.join(model_candidates)})")

    try:
        parsed, text, selected_model, llm_errors = _run_llm_candidates(
            client, model_candidates, prompt
        )
        if not parsed:
            arize_client.complete_span(
                trace_id=trace_id,
                span_id=llm_span["span_id"],
                inputs={"prompt": prompt},
                outputs={"raw_text": text},
                status="ERROR",
                metadata={"error": "; ".join(llm_errors) or "JSON parse failure"}
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
            
        normalized = _normalize(parsed, ticker, profile, incident, severity)
        
        arize_client.complete_span(
            trace_id=trace_id,
            span_id=llm_span["span_id"],
            inputs={"prompt": prompt},
            outputs=normalized,
            status="SUCCESS",
            metadata={"selected_model": selected_model},
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
