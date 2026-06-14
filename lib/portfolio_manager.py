"""Portfolio and watchlist helpers for Aegis_Codex serverless endpoints."""

from __future__ import annotations

import re
from typing import Iterable

import yfinance as yf


_INDIAN_SUFFIXES = (".NS", ".BO")
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
