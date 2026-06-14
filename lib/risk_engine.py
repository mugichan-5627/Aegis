"""Risk scoring helpers for Aegis_Codex."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


RISK_KEYWORDS = (
    "export control",
    "sanction",
    "sanctions",
    "military",
    "drawdown",
    "tariff",
    "ban",
    "supply chain",
    "geopolitical",
)

SECTOR_MAP = {
    # Semiconductors
    "NVDA": "Semiconductor", "TSM": "Semiconductor", "ASML": "Semiconductor",
    "AMAT": "Semiconductor", "INTC": "Semiconductor", "AMD": "Semiconductor",
    "QCOM": "Semiconductor", "AVGO": "Semiconductor", "MU": "Semiconductor",
    "LRCX": "Semiconductor", "KLAC": "Semiconductor", "MRVL": "Semiconductor",
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "GOOG": "Technology", "META": "Technology", "AMZN": "Technology",
    "NFLX": "Technology", "CRM": "Technology", "ORCL": "Technology",
    "IBM": "Technology", "CSCO": "Technology", "ADBE": "Technology",
    "NOW": "Technology", "SNOW": "Technology", "PLTR": "Technology",
    # Financial
    "JPM": "Financial Services", "BAC": "Financial Services", "GS": "Financial Services",
    "MS": "Financial Services", "WFC": "Financial Services", "C": "Financial Services",
    "BLK": "Financial Services", "AXP": "Financial Services", "V": "Financial Services",
    "MA": "Financial Services", "PYPL": "Financial Services",
    # Consumer
    "TSLA": "Consumer Cyclical", "F": "Consumer Cyclical", "GM": "Consumer Cyclical",
    "NKE": "Consumer Cyclical", "SBUX": "Consumer Cyclical", "MCD": "Consumer Cyclical",
    "AMZN": "Consumer Cyclical",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "BP": "Energy",
    "RELIANCE.NS": "Energy",
    # Healthcare
    "JNJ": "Healthcare", "PFE": "Healthcare", "MRNA": "Healthcare",
    "ABBV": "Healthcare", "UNH": "Healthcare", "LLY": "Healthcare",
    # Industrial
    "BA": "Industrial", "CAT": "Industrial", "GE": "Industrial",
    "HON": "Industrial", "LMT": "Industrial", "RTX": "Industrial",
    # Indian
    "TCS.NS": "Technology", "INFY.NS": "Technology", "HDFCBANK.NS": "Financial Services",
    "ICICIBANK.NS": "Financial Services", "SBIN.NS": "Financial Services",
}

SECTOR_OVERRIDES = SECTOR_MAP  # keep backward compat

REVENUE_RISK_DEFAULTS = {
    "NVDA": 38,
    "TSM": 55,
    "ASML": 21,
    "AMAT": 18,
    "JPM": 16,
    "RELIANCE.NS": 12,
}

FALLBACK_DESCRIPTIONS = {
    "NVDA": "US-China semiconductor export controls are pressuring advanced GPU demand. China datacenter exposure and compliance timing create an immediate stress event.",
    "TSM": "Cross-strait military posturing is raising fab interruption risk. Leading-edge production concentration in Taiwan keeps insurance and supply-chain exposure elevated.",
    "ASML": "EUV export license renewal risk is rising under US-Dutch review. China shipment exposure creates a regulatory stress path if licenses tighten.",
    "AMAT": "Semiconductor equipment export rules are tightening around China-bound tools. Shipment delays and compliance reviews could pressure near-term revenue.",
    "JPM": "Credit spread widening and market volatility are pressuring financial-sector risk appetite. Higher funding costs create a moderate bank stress case.",
    "RELIANCE.NS": "Energy and refining margins face macro volatility and tariff uncertainty. Imported input costs and FX pressure create watchlist-level exposure.",
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def compute_chaos_index(drawdown_pct: float, vix: float, keyword_hits: int) -> float:
    chaos = (
        0.4 * min(abs(drawdown_pct) / 15, 1)
        + 0.35 * min(vix / 40, 1)
        + 0.25 * min(keyword_hits / 60, 1)
    )
    return round(max(0.0, min(1.0, chaos)), 2)


def classify_severity(chaos_index: float) -> str:
    if chaos_index > 0.70:
        return "critical"
    if chaos_index > 0.50:
        return "elevated"
    if chaos_index > 0.30:
        return "watch"
    return "monitor"


def count_keyword_hits(results: Any) -> int:
    """Count weighted risk keyword hits in Tavily-style search results."""
    items = []
    if isinstance(results, dict):
        items = results.get("results") or []
    elif isinstance(results, list):
        items = results

    hits = 0
    for item in items:
        text = " ".join(
            str(item.get(key, ""))
            for key in ("title", "content", "snippet", "description", "url")
            if isinstance(item, dict)
        ).lower()
        for keyword in RISK_KEYWORDS:
            if keyword in text:
                hits += 1

    return min(99, hits * 4)


def fallback_keyword_hits(ticker: str) -> int:
    return {
        "NVDA": 47,
        "TSM": 41,
        "ASML": 28,
        "AMAT": 18,
        "JPM": 12,
        "RELIANCE.NS": 9,
    }.get(ticker.upper(), 8)


def revenue_at_risk(ticker: str) -> int:
    return REVENUE_RISK_DEFAULTS.get(ticker.upper(), 10)


def sector_label(ticker: str, yfinance_sector: str = "Unknown") -> str:
    """Prefer the live yfinance classification (works for US + Indian equities).

    The static SECTOR_MAP is only a fallback for when yfinance returns nothing
    (offline, rate-limited, or an unrecognised symbol), so real listings always
    get their accurate industry label rather than a coarse hardcoded override.
    """
    if yfinance_sector and yfinance_sector != "Unknown":
        return yfinance_sector
    return SECTOR_OVERRIDES.get(ticker.upper(), "Unknown")


def incident_description(ticker: str, sector: str, drawdown_pct: float, keyword_hits: int) -> str:
    fallback = FALLBACK_DESCRIPTIONS.get(ticker.upper())
    if fallback:
        return fallback
    return (
        f"{ticker.upper()} shows a {drawdown_pct:.1f}% five-day move with {keyword_hits} risk keyword matches. "
        f"{sector or 'Unknown'} exposure is being monitored for macro and supply-chain stress."
    )


def failure_incident(ticker: str, error: Exception | str, vix: float = 0.0) -> dict:
    timestamp = utc_timestamp()
    return {
        "ticker": ticker.upper(),
        "description": f"Live scan failed for {ticker.upper()}; serving a degraded incident record. Error: {str(error)[:120]}",
        "chaos_index": 0.0,
        "revenue_at_risk_pct": revenue_at_risk(ticker),
        "severity": "unknown",
        "sector": "Unknown",
        "drawdown_pct": 0.0,
        "vix": round(float(vix or 0), 1),
        "keyword_hits": 0,
        "timestamp": timestamp,
    }
