"""Serverless adversarial tribunal for Aegis_Codex.

Two-stage, evidence-grounded debate:

  Stage 0  Tavily  -> live, company-specific evidence (advanced search + sources)
  Stage 1  LLM     -> Bear builds an itemized risk dossier; Bull counters each risk
  Stage 2  LLM     -> a SEPARATE Judge reads both sides, weighs them, scores
                      probability-weighted scenarios and issues a directional
                      countermeasure + calibrated stress assumptions.

Every stage is its own Arize span, so the trace genuinely shows multiple model
calls. Deterministic guardrails (stress assumptions + recommendation derived from
chaos/severity/scores) keep the output sensible even if a model call fails.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from lib.local_telemetry import GLOBAL_TRACE_CONSOLE, arize_client


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
# Optional higher-reasoning model (e.g. meta/llama-3.3-70b-instruct). Tried first
# when set; the fast 8B remains the reliable fallback so the demo never stalls.
NVIDIA_QUALITY_MODEL = os.environ.get("NVIDIA_QUALITY_MODEL")

# Per-stage timeouts. The sum (Tavily + Stage 1 + Stage 2) stays under the 30s
# Vercel function budget; the frontend waits 29s. Stage 1 gets the most room
# because it carries the heaviest reasoning load. Tavily uses basic depth so the
# separate Judge call reliably has time to run within budget.
TAVILY_TIMEOUT_SECONDS = 6.0
STAGE1_TIMEOUT_SECONDS = 14.0
STAGE2_TIMEOUT_SECONDS = 10.0
# Hard wall: never let a model call push total wall-clock past this. The Judge
# gets whatever remains; if less than the floor is left it is synthesized
# deterministically so the function always returns inside the 30s budget.
WALL_BUDGET_SECONDS = 28.5
JUDGE_MIN_SECONDS = 4.5

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


# ----------------------------------------------------------------------------
# Company grounding
# ----------------------------------------------------------------------------
def _best_quote(ticker: str) -> dict | None:
    """One Yahoo symbol-search call; pick the best equity match, preferring the
    Indian .NS/.BO listing for bare Indian names. Works on Vercel (no auth crumb)
    where yfinance.info is blocked, so this is the reliable identity source."""
    from lib.portfolio_manager import _yahoo_search

    raw = (ticker or "").strip().upper()
    quotes = _yahoo_search(raw)
    if not quotes:
        return None
    by_symbol = {str(q.get("symbol", "")): q for q in quotes}
    for cand in (raw, f"{raw}.NS", f"{raw}.BO"):
        q = by_symbol.get(cand)
        if q and q.get("quoteType") == "EQUITY":
            return q
    equities = [q for q in quotes if q.get("quoteType") == "EQUITY"]
    return equities[0] if equities else None


def _company_profile(ticker: str) -> dict:
    """Resolve ANY US or Indian listed ticker to a grounding profile. Identity
    (name/sector/industry) comes from Yahoo search — reliable for bare Indian
    names (KOTAKBANK -> Kotak Mahindra Bank) and on Vercel where yfinance.info is
    blocked. yfinance then augments with financials/summary when available."""
    normalized = (ticker or "").upper()
    profile = dict(CURATED_COMPANY_PROFILES.get(normalized, {}))

    # 1. Canonical identity via Yahoo search (time-boxed so it can't eat budget).
    if not (profile.get("name") and profile.get("industry")):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
                match = _ex.submit(_best_quote, normalized).result(timeout=4.5)
            if match:
                profile.setdefault("symbol", str(match.get("symbol") or normalized))
                profile["name"] = profile.get("name") or match.get("longname") or match.get("shortname")
                profile["sector"] = profile.get("sector") or match.get("sector")
                profile["industry"] = profile.get("industry") or match.get("industry")
        except Exception:
            pass
    profile.setdefault("symbol", normalized)

    # 2. Optional financials/summary via yfinance on the RESOLVED symbol. Short
    #    time-box: blocked on Vercel (fast no-op), only augments locally.
    try:
        import yfinance as yf

        symbol = profile.get("symbol") or normalized
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
            info = _ex.submit(lambda: yf.Ticker(symbol).info or {}).result(timeout=2.5)
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
        "name", "sector", "industry", "country", "market_cap", "current_price",
        "revenue_growth", "ebitda_margin", "forward_pe", "beta",
        "business_model", "demand_drivers", "key_risks", "peers", "summary",
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


def _tavily_grounding(ticker: str, incident: str, profile: dict) -> dict:
    """Pull recent, real evidence via Tavily so the tribunal argues from
    company-specific facts. Uses advanced depth + Tavily's synthesized answer and
    returns structured sources for citation. Returns {} if Tavily is unavailable."""
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return {}
    name = str(profile.get("name") or ticker)
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=key)
        query = (
            f"{name} ({ticker}) stock risk: {incident}. earnings guidance, "
            f"regulation, competition, demand, margins, analyst estimates"
        )[:400]
        kwargs = dict(
            query=query,
            max_results=4,
            search_depth="basic",
            include_answer=True,
            topic="news",
        )
        try:
            result = client.search(timeout=TAVILY_TIMEOUT_SECONDS, **kwargs)
        except TypeError:
            result = client.search(**kwargs)
        if not isinstance(result, dict):
            return {}
        items = result.get("results") or []
        sources, lines = [], []
        for it in items[:6]:
            if not isinstance(it, dict):
                continue
            title = str(it.get("title") or "").strip()
            url = str(it.get("url") or "").strip()
            body = str(it.get("content") or it.get("snippet") or "").strip()
            if title or body:
                lines.append(f"- {title}: {body[:180]}")
            if title and url:
                sources.append({"title": title[:140], "url": url})
        answer = str(result.get("answer") or "").strip()
        return {
            "text": "\n".join(lines)[:1600],
            "answer": answer[:700],
            "sources": sources[:6],
        }
    except Exception:
        return {}


# ----------------------------------------------------------------------------
# Deterministic guardrails (used as fallback + sanity floor)
# ----------------------------------------------------------------------------
def _chaos_for_severity(severity: str) -> float:
    return {"critical": 0.8, "elevated": 0.62, "warning": 0.6, "watch": 0.45}.get(
        (severity or "watch").lower(), 0.5
    )


def _stress_from_signal(chaos_index: float, severity: str) -> dict:
    """Stress assumptions scaled by the live signal. A higher chaos index means a
    deeper haircut and a wider risk premium."""
    try:
        chaos = max(0.0, min(1.0, float(chaos_index)))
    except Exception:
        chaos = 0.5
    sev = (severity or "watch").lower()
    sev_floor = {"critical": 26.0, "elevated": 19.0, "warning": 19.0, "watch": 13.0}.get(sev, 16.0)
    haircut = round(sev_floor + chaos * 20.0, 1)
    margin = int(round(200 + chaos * 380))
    wacc = int(round(190 + chaos * 400))
    tg = round(-(0.5 + chaos * 1.8), 1)
    return {
        "revenue_haircut_pct": haircut,
        "margin_compression_bps": margin,
        "wacc_premium_bps": wacc,
        "terminal_growth_delta": tg,
    }


def _action_from_signal(bear_score: float, bull_score: float, chaos_index: float, severity: str) -> str:
    try:
        diff = float(bear_score) - float(bull_score)
    except Exception:
        diff = 0.0
    try:
        chaos = float(chaos_index)
    except Exception:
        chaos = 0.5
    sev = (severity or "watch").lower()
    if sev == "critical" or chaos >= 0.7 or diff >= 1.5:
        return "HEDGE"
    if chaos >= 0.5 or diff >= 0.5:
        return "REDUCE"
    if diff <= -1.0 and chaos < 0.45:
        return "ACCUMULATE"
    return "HOLD"


# ----------------------------------------------------------------------------
# JSON parsing / sanitizing
# ----------------------------------------------------------------------------
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


def _s(value: Any, limit: int = 320) -> str:
    return str(value if value is not None else "").strip()[:limit]


def _enum(value: Any, allowed: list[str], default: str) -> str:
    v = str(value or "").strip().lower()
    for a in allowed:
        if v == a or v.startswith(a):
            return a
    return default


def _clamp_score(value: Any, default: float) -> float:
    try:
        return round(max(0.0, min(10.0, float(value))), 1)
    except Exception:
        return default


# ----------------------------------------------------------------------------
# Prompts
# ----------------------------------------------------------------------------
_DEBATE_SYSTEM = (
    "You are Aegis_Codex, an institutional crisis-valuation tribunal that staffs a "
    "Bear analyst and a Bull analyst. You cover global equities — US and Indian (NSE/BSE) "
    "listings alike. You draw on your own knowledge of the SPECIFIC company named in the "
    "prompt: its real revenue segments, products, customers, geographies and named "
    "competitors, combined with the live evidence provided. Every claim is tied to one of "
    "those specifics. You never use filler like 'large liquid franchise', 'pricing power', "
    "'business mix' or 'core revenue streams' unless attached to a concrete, named fact. "
    "Never fabricate precise figures — if unsure of a number, argue the mechanism "
    "qualitatively. Return strict JSON only, no markdown."
)

_JUDGE_SYSTEM = (
    "You are the Black Swan Judge of the Aegis_Codex tribunal: an impartial CIO-level "
    "arbiter. You have just heard the Bear and the Bull. You decide which risks are "
    "real and material, assign probability-weighted scenarios, and issue a directional "
    "portfolio countermeasure (HEDGE / REDUCE / HOLD / ACCUMULATE) with calibrated "
    "stress assumptions. You do NOT recommend specific option structures, strikes or "
    "tenors — directional guidance and what to monitor only. Return strict JSON only."
)


def _debate_prompt(ticker, incident, chaos_index, severity, profile, news_block, answer_block) -> str:
    name = profile.get("name") or ticker
    sector = profile.get("industry") or profile.get("sector") or "its sector"
    profile_text = _format_company_context(profile)
    profile_block = f"\nCOMPANY PROFILE:\n{profile_text}\n" if profile_text else ""
    return f"""TARGET COMPANY: {name} (ticker {ticker}) — {sector}.

You are running an adversarial investment tribunal on {name}.
{profile_block}{news_block}{answer_block}
Incident under review: {incident}
Chaos index: {chaos_index} (0-1). Severity: {severity}.

Draw on your own knowledge of {name}'s ACTUAL business — its real revenue
segments, products, customers, geographies and named competitors — together with
the live evidence above. Name them specifically (real segment and competitor
names, not placeholders). If you are not certain of an exact figure, describe the
mechanism qualitatively instead of inventing a number.

The BEAR builds a concrete, itemized downside dossier: exactly THREE distinct,
company-specific risks, each naming the affected segment/product/customer/
geography, the transmission mechanism to revenue, margin or multiple, and the
evidence that would confirm it. The BULL must REBUT each of the bear's three
risks one-for-one: a genuine mitigant where one exists, otherwise an offsetting
bright-side, plus the asymmetry the market is missing.

Return ONLY valid JSON matching this schema (no markdown):
{{
  "bear": {{
    "thesis": "1-2 sentence company-specific downside thesis naming the exposed business",
    "risks": [
      {{"title":"short risk name","mechanism":"how it hits revenue/margin/multiple over 1-4 quarters","severity":"high|medium|low","horizon":"near|mid|structural","evidence":"the data/headline/figure that would confirm it"}},
      {{"title":"...","mechanism":"...","severity":"...","horizon":"...","evidence":"..."}},
      {{"title":"...","mechanism":"...","severity":"...","horizon":"...","evidence":"..."}}
    ],
    "score": 7.8
  }},
  "bull": {{
    "thesis": "1-2 sentence company-specific rebuttal thesis",
    "rebuttals": [
      {{"addresses":"<the exact bear risk title it answers>","type":"mitigant|bright_side","counter":"specific reason this risk is overstated or offset"}},
      {{"addresses":"...","type":"...","counter":"..."}},
      {{"addresses":"...","type":"...","counter":"..."}}
    ],
    "asymmetry":"the upside or mispricing the bear ignores, named specifically",
    "score": 6.4
  }}
}}

Scores are 0-10 conviction. Ground every field in {name}'s actual business and
the live evidence above — generic statements that could apply to any company are
rejected."""


def _judge_prompt(ticker, incident, chaos_index, severity, bear, bull, name="") -> str:
    risk_lines = "\n".join(
        f"  R{i+1}. {r.get('title','')} [{r.get('severity','')}/{r.get('horizon','')}]: {r.get('mechanism','')}"
        for i, r in enumerate(bear.get("risks", []))
    )
    rebut_lines = "\n".join(
        f"  vs {rb.get('addresses','')} ({rb.get('type','')}): {rb.get('counter','')}"
        for rb in bull.get("rebuttals", [])
    )
    who = f"{name} ({ticker})" if name and name != ticker else ticker
    return f"""You are judging the tribunal on {who}.
Incident: {incident}
Chaos index: {chaos_index} (0-1). Severity: {severity}.

BEAR thesis: {bear.get('thesis','')}
BEAR risks:
{risk_lines or '  (none provided)'}
BEAR conviction: {bear.get('score','?')}/10

BULL thesis: {bull.get('thesis','')}
BULL rebuttals:
{rebut_lines or '  (none provided)'}
BULL asymmetry: {bull.get('asymmetry','')}
BULL conviction: {bull.get('score','?')}/10

Weigh both sides impartially. Decide which bear risks survive the bull's
rebuttals, assign probability-weighted scenarios (probabilities sum to ~1.0),
and issue a directional countermeasure. Calibrate stress assumptions to THIS
company's risk, the severity ({severity}) and the chaos index ({chaos_index}) —
a higher chaos index implies a deeper haircut and wider premium. Do NOT name
option structures, strikes or tenors.

Return ONLY valid JSON (no markdown):
{{
  "judge": {{
    "verdict":"2-3 sentences: which side wins on the next 1-4 quarters and why, naming the decisive risk(s)",
    "key_risks_upheld":["bear risk title the market should price","another if material"],
    "scenarios":[
      {{"name":"Bear","probability":0.30,"outcome":"what happens to the stock / estimates"}},
      {{"name":"Base","probability":0.50,"outcome":"..."}},
      {{"name":"Bull","probability":0.20,"outcome":"..."}}
    ],
    "recommendation":{{
      "action":"HEDGE|REDUCE|HOLD|ACCUMULATE",
      "rationale":"why this action, tied to the upheld risks and probabilities",
      "monitor":["specific data point / catalyst that would change the view","another"],
      "invalidation":"the single observation that would flip this call"
    }},
    "score":9.0
  }},
  "proposed_assumptions":{{
    "revenue_haircut_pct": <number 0-60>,
    "margin_compression_bps": <integer 0-800>,
    "wacc_premium_bps": <integer 0-700>,
    "terminal_growth_delta": <negative number, e.g. -0.5 to -3.0>
  }}
}}"""


# ----------------------------------------------------------------------------
# LLM client + call
# ----------------------------------------------------------------------------
def _client_and_model() -> tuple[OpenAI | None, str | None]:
    openai_key = os.environ.get("OPENAI_API_KEY", None)
    if openai_key:
        return OpenAI(api_key=openai_key, timeout=STAGE1_TIMEOUT_SECONDS, max_retries=0), "gpt-4o"

    nvidia_key = os.environ.get("NVIDIA_API_KEY", None)
    if nvidia_key:
        return OpenAI(
            api_key=nvidia_key,
            base_url=NVIDIA_BASE_URL,
            timeout=STAGE1_TIMEOUT_SECONDS,
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
    if primary != "meta/llama-3.1-8b-instruct" and "nvidia" in NVIDIA_BASE_URL:
        candidates.append("meta/llama-3.1-8b-instruct")
    return list(dict.fromkeys(candidates))


def _run_llm(
    client: OpenAI,
    candidates: list[str],
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    timeout: float,
) -> tuple[dict | None, str, str | None, list[str]]:
    parsed, text = None, ""
    selected = candidates[0] if candidates else None
    errors: list[str] = []
    for candidate in candidates:
        kwargs = dict(
            model=candidate,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        try:
            try:
                response = client.chat.completions.create(
                    response_format={"type": "json_object"}, **kwargs
                )
            except Exception:
                response = client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content or ""
            parsed = _extract_json(text)
            if parsed:
                selected = candidate
                break
            errors.append(f"{candidate}: JSON parse failure")
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")
    return parsed, text, selected, errors


# ----------------------------------------------------------------------------
# Normalizers (LLM output -> safe, typed round objects)
# ----------------------------------------------------------------------------
def _norm_risk(item: dict) -> dict:
    item = item if isinstance(item, dict) else {}
    return {
        "title": _s(item.get("title") or item.get("name"), 90) or "Unspecified risk",
        "mechanism": _s(item.get("mechanism") or item.get("detail"), 400),
        "severity": _enum(item.get("severity"), ["high", "medium", "low"], "medium"),
        "horizon": _enum(item.get("horizon"), ["near", "mid", "structural"], "near"),
        "evidence": _s(item.get("evidence") or item.get("watch"), 260),
    }


def _norm_rebuttal(item: dict) -> dict:
    item = item if isinstance(item, dict) else {}
    return {
        "addresses": _s(item.get("addresses") or item.get("risk"), 90),
        "type": _enum(item.get("type"), ["mitigant", "bright_side"], "mitigant"),
        "counter": _s(item.get("counter") or item.get("text"), 400),
    }


def _norm_scenario(item: dict, default_name: str) -> dict:
    item = item if isinstance(item, dict) else {}
    try:
        prob = float(item.get("probability", 0))
        if prob > 1:
            prob = prob / 100.0
        prob = max(0.0, min(1.0, prob))
    except Exception:
        prob = 0.0
    return {
        "name": _s(item.get("name"), 24) or default_name,
        "probability": round(prob, 2),
        "outcome": _s(item.get("outcome") or item.get("detail"), 240),
    }


def _compose_bear_text(bear: dict) -> str:
    parts = [bear.get("thesis", "").strip()]
    for i, r in enumerate(bear.get("risks", [])):
        parts.append(f"Risk {i+1} — {r['title']}: {r['mechanism']}")
    return " ".join(p for p in parts if p)[:1600]


def _compose_bull_text(bull: dict) -> str:
    parts = [bull.get("thesis", "").strip()]
    for rb in bull.get("rebuttals", []):
        verb = "Offset" if rb["type"] == "bright_side" else "Mitigant"
        parts.append(f"{verb} on {rb['addresses']}: {rb['counter']}")
    if bull.get("asymmetry"):
        parts.append(f"Asymmetry: {bull['asymmetry']}")
    return " ".join(p for p in parts if p)[:1600]


def _compose_judge_text(judge: dict) -> str:
    rec = judge.get("recommendation", {})
    parts = [judge.get("verdict", "").strip()]
    scen = judge.get("scenarios", [])
    if scen:
        parts.append(
            "Scenarios: "
            + "; ".join(f"{s['name']} {int(round(s['probability']*100))}% — {s['outcome']}" for s in scen)
        )
    action = rec.get("action", "HOLD")
    rationale = rec.get("rationale", "")
    parts.append(f"RECOMMENDATION - {action}: {rationale}".strip())
    return " ".join(p for p in parts if p)[:1600]


def _build_bear_round(bear: dict, fb: dict) -> dict:
    bear = bear if isinstance(bear, dict) else {}
    risks = [_norm_risk(r) for r in (bear.get("risks") or [])][:3]
    if len(risks) < 2:  # too thin -> use fallback dossier
        risks = fb["bear"]["risks"]
        thesis = fb["bear"]["thesis"]
        score = fb["bear"]["score"]
    else:
        thesis = _s(bear.get("thesis"), 360) or fb["bear"]["thesis"]
        score = _clamp_score(bear.get("score"), fb["bear"]["score"])
    out = {"role": "bear", "label": "Bear Analyst", "thesis": thesis, "risks": risks, "score": score}
    out["text"] = _compose_bear_text(out)
    return out


def _build_bull_round(bull: dict, fb: dict) -> dict:
    bull = bull if isinstance(bull, dict) else {}
    rebuttals = [_norm_rebuttal(r) for r in (bull.get("rebuttals") or [])][:3]
    if len(rebuttals) < 2:
        rebuttals = fb["bull"]["rebuttals"]
        thesis = fb["bull"]["thesis"]
        asymmetry = fb["bull"]["asymmetry"]
        score = fb["bull"]["score"]
    else:
        thesis = _s(bull.get("thesis"), 360) or fb["bull"]["thesis"]
        asymmetry = _s(bull.get("asymmetry"), 360) or fb["bull"]["asymmetry"]
        score = _clamp_score(bull.get("score"), fb["bull"]["score"])
    out = {"role": "bull", "label": "Bull Analyst", "thesis": thesis,
           "rebuttals": rebuttals, "asymmetry": asymmetry, "score": score}
    out["text"] = _compose_bull_text(out)
    return out


def _build_judge_round(judge: dict, fb: dict, bear_score: float, bull_score: float,
                       chaos_index: float, severity: str) -> dict:
    judge = judge if isinstance(judge, dict) else {}
    rec_in = judge.get("recommendation") if isinstance(judge.get("recommendation"), dict) else {}
    scenarios = [_norm_scenario(s, n) for s, n in zip(
        judge.get("scenarios") or [], ["Bear", "Base", "Bull"])][:3]
    if not scenarios:
        scenarios = fb["judge"]["scenarios"]

    verdict = _s(judge.get("verdict"), 700) or fb["judge"]["verdict"]
    upheld = [_s(x, 90) for x in (judge.get("key_risks_upheld") or []) if _s(x, 90)][:3]
    if not upheld:
        upheld = fb["judge"]["key_risks_upheld"]

    action = _enum(rec_in.get("action"), ["hedge", "reduce", "hold", "accumulate"],
                   _action_from_signal(bear_score, bull_score, chaos_index, severity).lower()).upper()
    monitor = [_s(x, 160) for x in (rec_in.get("monitor") or []) if _s(x, 160)][:3]
    if not monitor:
        monitor = fb["judge"]["recommendation"]["monitor"]
    recommendation = {
        "action": action,
        "rationale": _s(rec_in.get("rationale"), 400) or fb["judge"]["recommendation"]["rationale"],
        "monitor": monitor,
        "invalidation": _s(rec_in.get("invalidation"), 240) or fb["judge"]["recommendation"]["invalidation"],
    }
    out = {
        "role": "judge", "label": "Black Swan Judge", "verdict": verdict,
        "key_risks_upheld": upheld, "scenarios": scenarios,
        "recommendation": recommendation,
        "score": _clamp_score(judge.get("score"), fb["judge"]["score"]),
    }
    out["text"] = _compose_judge_text(out)
    return out


def _clean_assumptions(raw: Any, default: dict) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key, dval in default.items():
        try:
            out[key] = round(float(raw.get(key, dval)), 1)
        except Exception:
            out[key] = dval
    # Sanity floors so a lazy model can't return a no-op stress.
    out["revenue_haircut_pct"] = max(0.0, min(60.0, out["revenue_haircut_pct"]))
    out["margin_compression_bps"] = int(max(0, min(800, out["margin_compression_bps"])))
    out["wacc_premium_bps"] = int(max(0, min(700, out["wacc_premium_bps"])))
    out["terminal_growth_delta"] = max(-4.0, min(0.0, out["terminal_growth_delta"]))
    return out


# ----------------------------------------------------------------------------
# Deterministic, structured fallback (also analyst-grade)
# ----------------------------------------------------------------------------
# Sector-specific risk hints so the deterministic fallback is industry-aware for
# ANY ticker, not generic boilerplate. Matched by substring against industry/sector.
_SECTOR_RISK_HINTS = {
    "bank": ["net interest margin compression", "credit cost and asset-quality normalization", "deposit competition and funding cost"],
    "financ": ["credit cycle and asset quality", "rate sensitivity and spread compression", "regulatory capital requirements"],
    "insur": ["claims and underwriting losses", "investment-yield pressure", "regulatory solvency capital"],
    "semiconduct": ["demand digestion and inventory correction", "customer and order concentration", "export-control and China exposure"],
    "oil": ["commodity price and refining-margin swings", "regulatory and windfall-tax risk", "energy-transition demand shift"],
    "gas": ["commodity price and refining-margin swings", "regulatory and windfall-tax risk", "energy-transition demand shift"],
    "energy": ["commodity-price volatility", "regulatory and tax risk", "energy-transition demand shift"],
    "pharma": ["pricing and reimbursement pressure", "regulatory/USFDA and patent risk", "pipeline and approval timing"],
    "drug": ["pricing and reimbursement pressure", "regulatory and patent-cliff risk", "pipeline and approval timing"],
    "health": ["reimbursement and pricing pressure", "regulatory risk", "utilization and cost trends"],
    "auto": ["demand cyclicality and inventory", "input-cost and margin pressure", "EV-transition capex and competition"],
    "software": ["growth deceleration and churn", "AI-capex monetization lag", "valuation-multiple compression"],
    "technolog": ["growth deceleration", "competitive disruption", "valuation-multiple compression"],
    "internet": ["user-growth and engagement plateau", "ad-spend cyclicality", "regulatory and privacy risk"],
    "retail": ["consumer-demand softness", "margin and inventory risk", "e-commerce and competitive pressure"],
    "aerospace": ["program execution and delivery delays", "defense-budget and order timing", "supply-chain bottlenecks"],
    "consumer": ["volume and pricing softness", "input-cost inflation", "private-label and competitive pressure"],
    "industrial": ["cyclical demand softness", "order backlog and book-to-bill", "input-cost pressure"],
    "telecom": ["ARPU and pricing pressure", "spectrum and capex intensity", "competitive subscriber churn"],
    "real estate": ["rate sensitivity and cap-rate expansion", "occupancy and leasing risk", "refinancing and leverage"],
    "metal": ["commodity-price and spread volatility", "demand cyclicality", "input-cost and energy pressure"],
    "material": ["commodity-price and spread volatility", "demand cyclicality", "input-cost pressure"],
}


def _sector_risks(industry: str, sector: str) -> list[str]:
    text = f"{industry} {sector}".lower()
    for key, risks in _SECTOR_RISK_HINTS.items():
        if key in text:
            return list(risks[:3])
    return [
        "estimate cuts as forward guidance resets",
        "margin pressure and cost deleverage",
        "multiple compression as the risk premium rises",
    ]


def _structured_fallback(ticker: str, incident: str, severity: str, chaos_index: float, profile: dict) -> dict:
    name = profile.get("name") or ticker
    industry = profile.get("industry") or profile.get("sector") or "its sector"
    business = _clean_fragment(
        profile.get("business_model") or profile.get("summary")
        or (f"its {industry} operations" if industry != "its sector" else "its core revenue streams")
    )
    demand = _clean_fragment(profile.get("demand_drivers") or f"demand across {industry}")
    peers = _clean_fragment(profile.get("peers") or "direct competitors")
    sev = (severity or "watch").lower()
    trig = incident.strip().rstrip(".") or "the live Watchtower signal"

    if profile.get("key_risks"):
        risk_tokens = [t.strip() for t in re.split(r",|;| and ", _clean_fragment(profile["key_risks"])) if t.strip()][:3]
    else:
        risk_tokens = _sector_risks(industry, profile.get("sector") or "")
    while len(risk_tokens) < 3:
        risk_tokens.append("multiple compression as expectations reset")
    bear_risks = [
        {
            "title": tok[:80].capitalize(),
            "mechanism": f"The incident reads through to {demand}; {tok} pressures {ticker}'s forward revenue or margin over the next 1-4 quarters before management can prove resilience.",
            "severity": "high" if (sev == "critical" or i == 0) else "medium",
            "horizon": "near" if i < 2 else "structural",
            "evidence": f"Watch {ticker} guidance, segment commentary and order activity versus {peers}.",
        }
        for i, tok in enumerate(risk_tokens)
    ]
    bull_rebuttals = [
        {
            "addresses": r["title"],
            "type": "mitigant" if i % 2 == 0 else "bright_side",
            "counter": f"{ticker}'s position in {business} can absorb this if {demand} stays intact; the move may be positioning rather than impairment until lost share or cancelled demand is confirmed.",
        }
        for i, r in enumerate(bear_risks)
    ]
    bear_score = 8.0 if sev == "critical" else 7.3
    bull_score = 6.3
    action = _action_from_signal(bear_score, bull_score, chaos_index, severity)

    fb = {
        "bear": {
            "thesis": f"{ticker} ({name}) is a {industry} case, not a generic macro proxy; {trig} hits a business built on {business}.",
            "risks": bear_risks,
            "score": bear_score,
        },
        "bull": {
            "thesis": f"{ticker}'s rebuttal rests on the durability of {business}; the bear haircut should stay probabilistic without proof of structural damage.",
            "rebuttals": bull_rebuttals,
            "asymmetry": f"If {demand} holds, normalized earnings power versus {peers} is unchanged and the selloff overstates the structural impact.",
            "score": bull_score,
        },
        "judge": {
            "verdict": f"The tribunal gives {ticker} a cautious but non-terminal verdict at chaos {chaos_index}: the Bear wins the next-quarter timing argument through {risk_tokens[0].lower()}, while the Bull case survives only if {demand} keeps supporting forward expectations.",
            "key_risks_upheld": [bear_risks[0]["title"], bear_risks[1]["title"]],
            "scenarios": [
                {"name": "Bear", "probability": 0.35 if sev == "critical" else 0.30, "outcome": f"Estimates and multiple reset as {risk_tokens[0].lower()} plays out."},
                {"name": "Base", "probability": 0.45, "outcome": f"{ticker} absorbs the shock with a temporary haircut; {demand} stabilizes."},
                {"name": "Bull", "probability": 0.20 if sev == "critical" else 0.25, "outcome": f"Signal proves to be positioning noise; {ticker} re-rates with {peers}."},
            ],
            "recommendation": {
                "action": action,
                "rationale": f"At chaos {chaos_index} and {sev} severity the upheld risks justify a {action.lower()} stance until live indicators confirm whether this is cyclic noise or an expectation reset.",
                "monitor": [
                    f"{ticker} forward guidance and segment order commentary",
                    f"Relative price action and estimate revisions versus {peers}",
                ],
                "invalidation": f"Confirmed stable demand, intact margins and no guidance cut would flip the call toward HOLD/ACCUMULATE.",
            },
            "score": 8.6,
        },
    }
    return fb


def _fallback(ticker: str, incident: str = "", severity: str = "") -> dict:
    """Full, structured fallback debate (used when no LLM is available or a stage
    fails). Returns the same rich schema as the live path."""
    normalized = (ticker or "NVDA").upper()
    profile = _company_profile(normalized)
    chaos = _chaos_for_severity(severity)
    fb = _structured_fallback(normalized, incident, severity, chaos, profile)
    bear = _build_bear_round({}, fb)
    bull = _build_bull_round({}, fb)
    judge = _build_judge_round({}, fb, bear["score"], bull["score"], chaos, severity)
    assumptions = _clean_assumptions(_stress_from_signal(chaos, severity), DEFAULT_ASSUMPTIONS)
    return {
        "rounds": [bear, bull, judge],
        "proposed_assumptions": assumptions,
        "recommendation": judge["recommendation"],
        "bear_score": bear["score"],
        "bull_score": bull["score"],
        "sources": [],
        "grounded": False,
    }


# ----------------------------------------------------------------------------
# Telemetry helper
# ----------------------------------------------------------------------------
def _snapshot_trace(trace_id: str) -> dict | None:
    for t in GLOBAL_TRACE_CONSOLE:
        if t["trace_id"] != trace_id:
            continue
        return {
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
    return None


def _attach_fallback(ticker, incident, severity, trace_id) -> dict:
    arize_client.complete_trace(trace_id=trace_id)
    res = _fallback(ticker, incident, severity)
    res["telemetry"] = _snapshot_trace(trace_id)
    return res


# ----------------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------------
def run_tribunal(ticker: str, incident: str, chaos_index: float, severity: str) -> dict:
    """Run the two-stage Bear/Bull -> Judge tribunal with NVIDIA/OpenAI, falling
    back to a deterministic structured debate when models are unavailable."""
    ticker = (ticker or "NVDA").upper()
    t0 = time.monotonic()

    trace = arize_client.create_trace(name=f"Tribunal Debate: {ticker}", ticker=ticker)
    trace_id = trace["trace_id"]

    client, model = _client_and_model()
    profile = _company_profile(ticker)

    if not client or not model:
        return _attach_fallback(ticker, incident, severity, trace_id)

    # --- Stage 0: live grounding -------------------------------------------
    news_span = arize_client.start_span(trace_id=trace_id, name="Tavily News Retrieval")
    grounding = _tavily_grounding(ticker, incident, profile)
    news = grounding.get("text", "")
    answer = grounding.get("answer", "")
    sources = grounding.get("sources", [])
    arize_client.complete_span(
        trace_id=trace_id, span_id=news_span["span_id"],
        inputs={"ticker": ticker, "incident": incident},
        outputs={"headlines": news[:800] if news else "(none)", "sources": len(sources)},
        status="SUCCESS" if news else "SKIPPED",
    )

    news_block = (
        "\nLIVE NEWS EVIDENCE (cite specific facts, figures, products, customers, "
        f"geographies — do NOT write generic statements):\n{news}\n" if news else ""
    )
    answer_block = (f"\nSEARCH SYNTHESIS: {answer}\n" if answer else "")

    candidates = _model_candidates(model)
    fb = _structured_fallback(ticker, incident, severity, chaos_index, profile)

    # --- Stage 1: Bear + Bull adversarial debate ---------------------------
    s1_span = arize_client.start_span(
        trace_id=trace_id, name=f"Stage 1 - Bear vs Bull ({' -> '.join(candidates)})")
    debate_prompt = _debate_prompt(ticker, incident, chaos_index, severity,
                                   profile, news_block, answer_block)
    parsed1, raw1, model1, errs1 = _run_llm(
        client, candidates, _DEBATE_SYSTEM, debate_prompt,
        max_tokens=720, timeout=STAGE1_TIMEOUT_SECONDS)

    if not parsed1:
        arize_client.complete_span(
            trace_id=trace_id, span_id=s1_span["span_id"],
            inputs={"prompt": debate_prompt[:400]}, outputs={"raw": raw1[:400]},
            status="ERROR", metadata={"error": "; ".join(errs1) or "parse failure"})
        return _attach_fallback(ticker, incident, severity, trace_id)

    bear = _build_bear_round(parsed1.get("bear", {}), fb)
    bull = _build_bull_round(parsed1.get("bull", {}), fb)
    arize_client.complete_span(
        trace_id=trace_id, span_id=s1_span["span_id"],
        inputs={"ticker": ticker, "incident": incident},
        outputs={"bear": bear["text"], "bull": bull["text"]},
        status="SUCCESS", metadata={"selected_model": model1})

    # --- Stage 2: separate, impartial Judge --------------------------------
    # Always attempt the real second call whenever enough wall-clock remains;
    # the timeout is sized to the time left so the function stays under budget.
    remaining = WALL_BUDGET_SECONDS - (time.monotonic() - t0)
    judge_raw = None
    if remaining >= JUDGE_MIN_SECONDS:
        s2_span = arize_client.start_span(
            trace_id=trace_id, name=f"Stage 2 - Black Swan Judge ({model1})")
        judge_prompt = _judge_prompt(ticker, incident, chaos_index, severity, bear, bull,
                                     name=profile.get("name") or ticker)
        j_timeout = min(STAGE2_TIMEOUT_SECONDS, remaining)
        parsed2, raw2, model2, errs2 = _run_llm(
            client, [model1], _JUDGE_SYSTEM, judge_prompt,
            max_tokens=560, timeout=j_timeout)
        if parsed2:
            judge_raw = parsed2
            arize_client.complete_span(
                trace_id=trace_id, span_id=s2_span["span_id"],
                inputs={"bear": bear["text"][:200], "bull": bull["text"][:200]},
                outputs={"judge": str(parsed2.get("judge", {}))[:400]},
                status="SUCCESS", metadata={"selected_model": model2})
        else:
            arize_client.complete_span(
                trace_id=trace_id, span_id=s2_span["span_id"],
                inputs={"prompt": judge_prompt[:300]}, outputs={"raw": raw2[:300]},
                status="ERROR", metadata={"error": "; ".join(errs2) or "parse failure"})
    # else: over budget — synthesize the judge deterministically below.

    judge = _build_judge_round(
        (judge_raw or {}).get("judge", {}), fb, bear["score"], bull["score"],
        chaos_index, severity)

    floor = _stress_from_signal(chaos_index, severity)
    if judge_raw and judge_raw.get("proposed_assumptions"):
        assumptions = _clean_assumptions(judge_raw["proposed_assumptions"], DEFAULT_ASSUMPTIONS)
        # Honour the live signal: chaos/severity set a floor so a lowballing judge
        # can never soften stress below what the signal implies. A higher chaos
        # index therefore always produces a deeper haircut and wider premium.
        assumptions["revenue_haircut_pct"] = max(assumptions["revenue_haircut_pct"], floor["revenue_haircut_pct"])
        assumptions["margin_compression_bps"] = max(assumptions["margin_compression_bps"], floor["margin_compression_bps"])
        assumptions["wacc_premium_bps"] = max(assumptions["wacc_premium_bps"], floor["wacc_premium_bps"])
        assumptions["terminal_growth_delta"] = min(assumptions["terminal_growth_delta"], floor["terminal_growth_delta"])
    else:
        assumptions = _clean_assumptions(floor, DEFAULT_ASSUMPTIONS)

    # --- per-role spans (so each advocate shows in the trace) --------------
    for r in (bear, bull, judge):
        rs = arize_client.start_span(trace_id=trace_id, name=f"Swarm Segment: {r['label']}")
        arize_client.complete_span(
            trace_id=trace_id, span_id=rs["span_id"],
            inputs={"ticker": ticker, "role": r["role"]},
            outputs={"text": r["text"], "score": r["score"]}, status="SUCCESS")

    arize_client.complete_trace(trace_id=trace_id)

    return {
        "rounds": [bear, bull, judge],
        "proposed_assumptions": assumptions,
        "recommendation": judge["recommendation"],
        "bear_score": bear["score"],
        "bull_score": bull["score"],
        "sources": sources,
        "grounded": bool(news),
        "telemetry": _snapshot_trace(trace_id),
    }
