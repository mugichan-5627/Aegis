"""Portfolio and watchlist helpers for Aegis_Codex serverless endpoints."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Iterable

import yfinance as yf


_INDIAN_SUFFIXES = (".NS", ".BO")
_YF_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_KNOWN_INDIAN_TICKERS = {
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "LT",
    "ITC",
    "BHARTIARTL",
}


def normalize_ticker(ticker: str) -> str:
    """Uppercase and strip whitespace, appending .NS for known Indian tickers."""
    cleaned = (ticker or "").strip().upper()
    if cleaned in _KNOWN_INDIAN_TICKERS:
        return f"{cleaned}.NS"
    return cleaned


def validate_watchlist(tickers: list) -> list:
    """Remove duplicates, validate simple ticker format, cap at 10, return cleaned list."""
    seen: set[str] = set()
    cleaned: list[str] = []

    for raw in tickers or []:
        ticker = normalize_ticker(str(raw))
        if not ticker or ticker in seen:
            continue
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,14}", ticker):
            continue
        seen.add(ticker)
        cleaned.append(ticker)
        if len(cleaned) >= 10:
            break

    return cleaned


def compute_portfolio_beta(tickers: Iterable[str]) -> float:
    """Fetch ticker betas and return an equal-weighted average."""
    betas: list[float] = []
    for ticker in validate_watchlist(list(tickers)):
        try:
            beta = yf.Ticker(ticker).info.get("beta")
            if beta is not None:
                betas.append(float(beta))
        except Exception:
            continue
    return round(sum(betas) / len(betas), 2) if betas else 1.0


def _yahoo_search(query: str) -> list:
    """Yahoo symbol search — resolves any US/Indian name to its canonical symbol
    and (for equities) returns sector/industry, with no auth crumb. Reliable on
    Vercel serverless where yfinance's quote/info endpoints get blocked."""
    for host in ("query2.finance.yahoo.com", "query1.finance.yahoo.com"):
        try:
            url = (
                f"https://{host}/v1/finance/search?q={urllib.parse.quote(query)}"
                "&quotesCount=6&newsCount=0"
            )
            req = urllib.request.Request(url, headers={"User-Agent": _YF_UA})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            quotes = data.get("quotes") or []
            if quotes:
                return quotes
        except Exception:
            continue
    return []


def _symbol_has_data(symbol: str) -> bool:
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        try:
            url = f"https://{host}/v8/finance/chart/{symbol}?range=1d&interval=1d"
            req = urllib.request.Request(url, headers={"User-Agent": _YF_UA})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if ((data.get("chart") or {}).get("result")):
                return True
        except Exception:
            continue
    return False


def _label_from_quote(q: dict) -> str:
    """Prefer the granular industry, fall back to broad sector."""
    return str(q.get("industry") or q.get("sector") or "Unknown")


def resolve_ticker(ticker: str) -> dict:
    """Resolve a user-typed ticker to {symbol, sector} for any US or Indian
    listing. Bare Indian names (e.g. KOTAKBANK) get their .NS/.BO suffix so
    price data and sector populate instead of showing 0% / Unknown."""
    cleaned = (ticker or "").strip().upper()
    if not cleaned:
        return {"symbol": cleaned, "sector": "Unknown"}
    if cleaned in _KNOWN_INDIAN_TICKERS:
        cleaned = f"{cleaned}.NS"

    quotes = _yahoo_search(cleaned)
    by_symbol = {str(q.get("symbol", "")): q for q in quotes if q.get("symbol")}

    # Candidate symbols in order of preference.
    if "." in cleaned:
        candidates = [cleaned]
    else:
        candidates = [cleaned, f"{cleaned}.NS", f"{cleaned}.BO"]

    # 1. Exact match present in search results (carries sector/industry).
    for cand in candidates:
        if cand in by_symbol:
            return {"symbol": cand, "sector": _label_from_quote(by_symbol[cand])}

    # 2. Verify a candidate directly against the price endpoint.
    for cand in candidates:
        if _symbol_has_data(cand):
            sector = _label_from_quote(by_symbol.get(cand, {}))
            return {"symbol": cand, "sector": sector}

    # 3. Fall back to the best equity the search returned.
    equities = [q for q in quotes if q.get("quoteType") == "EQUITY"]
    if equities:
        return {"symbol": str(equities[0]["symbol"]), "sector": _label_from_quote(equities[0])}

    return {"symbol": cleaned, "sector": "Unknown"}


def get_sector(ticker: str) -> str:
    """Return the most specific yfinance classification for a listed equity.

    Prefers the granular ``industry`` field (e.g. "Aerospace & Defense",
    "Semiconductors", "Oil & Gas Refining & Marketing") over the broad
    ``sector`` field (e.g. "Industrials"), since the industry label is far more
    informative and is populated for both US and Indian (.NS / .BO) listings.
    Falls back to ``sector``, then "Unknown".
    """
    try:
        info = yf.Ticker(normalize_ticker(ticker)).info
        industry = info.get("industry")
        if industry:
            return str(industry)
        sector = info.get("sector")
        if sector:
            return str(sector)
    except Exception:
        pass
    return "Unknown"
