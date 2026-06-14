from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

import yfinance as yf
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.portfolio_manager import get_sector, validate_watchlist
from lib.risk_engine import (
    compute_chaos_index,
    classify_severity,
    count_keyword_hits,
    fallback_keyword_hits,
    failure_incident,
    incident_description,
    revenue_at_risk,
    sector_label,
    utc_timestamp,
)
from lib.local_telemetry import GLOBAL_TRACE_CONSOLE, arize_client


load_dotenv(ROOT / ".env")

def _get_cache_path(filename: str) -> Path:
    p = Path(f"/tmp/{filename}")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        test_file = p.parent / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        return p
    except Exception:
        fallback = ROOT / "tmp" / filename
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback

CACHE_FILE = _get_cache_path("aegis_last_scan.json")


def _save_cache(payload: dict) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(payload))
    except Exception:
        pass


def _load_cache() -> dict | None:
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text())
    except Exception:
        pass
    return None


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


import urllib.request

# yfinance's default requests get rate-limited / blocked on Vercel serverless,
# which silently returns empty history (every drawdown shows 0.0%). Hitting
# Yahoo's public chart endpoint with a browser User-Agent is far more reliable
# there and needs no auth crumb. yfinance stays as a local fallback.
_YF_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _yahoo_series(ticker: str, rng: str = "5d", interval: str = "1d") -> dict | None:
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        try:
            url = (
                f"https://{host}/v8/finance/chart/{ticker}"
                f"?range={rng}&interval={interval}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": _YF_UA})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = (data.get("chart") or {}).get("result") or []
            if results:
                return results[0]
        except Exception:
            continue
    return None


def _vix() -> float:
    series = _yahoo_series("^VIX", "5d", "1d")
    if series:
        try:
            closes = [c for c in series["indicators"]["quote"][0].get("close", []) if c is not None]
            if closes:
                return round(float(closes[-1]), 1)
            price = (series.get("meta") or {}).get("regularMarketPrice")
            if price:
                return round(float(price), 1)
        except Exception:
            pass
    try:
        hist = yf.Ticker("^VIX").history(period="1d")
        close = hist["Close"].dropna()
        if not close.empty:
            return round(float(close.iloc[-1]), 1)
    except Exception:
        pass
    return 28.4


def _drawdown(ticker: str) -> float:
    series = _yahoo_series(ticker, "5d", "1d")
    if series:
        try:
            quote = series["indicators"]["quote"][0]
            opens = [o for o in quote.get("open", []) if o is not None]
            closes = [c for c in quote.get("close", []) if c is not None]
            if opens and closes and opens[0]:
                return round((closes[-1] - opens[0]) / opens[0] * 100, 1)
        except Exception:
            pass
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        if hist is not None and not hist.empty:
            open_5d = float(hist["Open"].dropna().iloc[0])
            latest_close = float(hist["Close"].dropna().iloc[-1])
            if open_5d:
                return round((latest_close - open_5d) / open_5d * 100, 1)
    except Exception:
        pass
    return 0.0


def _tavily_hits(ticker: str) -> int:
    key = os.environ.get("TAVILY_API_KEY", None)
    if not key:
        return fallback_keyword_hits(ticker)
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=key)
        query = (
            f"{ticker} export control OR sanctions OR geopolitical OR supply chain risk "
            "site:reuters.com OR site:bloomberg.com"
        )
        result = client.search(query=query, max_results=8, search_depth="basic")
        hits = count_keyword_hits(result)
        return hits if hits > 0 else fallback_keyword_hits(ticker)
    except Exception:
        return fallback_keyword_hits(ticker)


def scan_ticker(ticker: str, vix: float) -> dict:
    drawdown_pct = _drawdown(ticker)
    keyword_hits = _tavily_hits(ticker)
    chaos = compute_chaos_index(drawdown_pct, vix, keyword_hits)
    sector = sector_label(ticker, get_sector(ticker))
    return {
        "ticker": ticker,
        "description": incident_description(ticker, sector, drawdown_pct, keyword_hits),
        "chaos_index": chaos,
        "revenue_at_risk_pct": revenue_at_risk(ticker),
        "severity": classify_severity(chaos),
        "sector": sector,
        "drawdown_pct": drawdown_pct,
        "vix": round(float(vix), 1),
        "keyword_hits": int(keyword_hits),
        "timestamp": utc_timestamp(),
    }


def handle(payload: dict[str, Any]) -> dict:
    tickers = validate_watchlist(payload.get("tickers") or ["NVDA", "TSM", "ASML", "AMAT", "RELIANCE.NS"])
    if not tickers:
        tickers = ["NVDA", "TSM", "ASML", "AMAT", "RELIANCE.NS"]

    vix = _vix()
    
    # 1. Initialize Arize trace
    trace = arize_client.create_trace(name="Grounded Watchlist Scan", ticker=",".join(tickers))
    trace_id = trace["trace_id"]
    
    incidents = []
    for ticker in tickers:
        # Start a span for each ticker
        span = arize_client.start_span(trace_id=trace_id, name=f"Scan Ticker: {ticker}")
        try:
            inc = scan_ticker(ticker, vix)
            incidents.append(inc)
            arize_client.complete_span(
                trace_id=trace_id,
                span_id=span["span_id"],
                inputs={"ticker": ticker, "vix": vix},
                outputs=inc,
                status="SUCCESS"
            )
        except Exception as exc:
            inc = failure_incident(ticker, exc, vix)
            incidents.append(inc)
            arize_client.complete_span(
                trace_id=trace_id,
                span_id=span["span_id"],
                inputs={"ticker": ticker, "vix": vix},
                outputs=inc,
                status="ERROR",
                metadata={"error": str(exc)}
            )

    # 2. Finalize Arize trace
    arize_client.complete_trace(trace_id=trace_id)
    
    # Extract trace from memory store to return to frontend
    matching_trace = None
    for t in GLOBAL_TRACE_CONSOLE:
        if t["trace_id"] == trace_id:
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

    result = {
        "incidents": incidents,
        "macro": {"vix": round(float(vix), 1), "scan_timestamp": utc_timestamp()},
        "telemetry": matching_trace,
    }
    _save_cache(result)

    # Auto-trigger tribunal for the first critical incident found
    critical = [inc for inc in incidents if inc.get("severity") == "critical"]
    if critical:
        _auto_tribunal(critical[0])

    return result


def _auto_tribunal(incident: dict) -> None:
    """Run tribunal in background for a critical incident and cache the result."""
    try:
        from lib.agent_swarm import run_tribunal

        tribunal_cache = _get_cache_path("aegis_last_tribunal.json")
        result = run_tribunal(
            ticker=incident["ticker"],
            incident=incident["description"],
            chaos_index=float(incident.get("chaos_index", 0.5)),
            severity=incident.get("severity", "critical"),
        )
        result["_auto"] = True
        result["_ticker"] = incident["ticker"]
        tribunal_cache.write_text(json.dumps(result))
    except Exception:
        pass


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        _json_response(self, {"ok": True})

    def do_GET(self) -> None:
        cached = _load_cache()
        if cached:
            _json_response(self, {**cached, "cached": True})
        else:
            _json_response(self, {"incidents": [], "macro": {}, "cached": False})

    def do_POST(self) -> None:
        try:
            _json_response(self, handle(_read_json(self)))
        except Exception as exc:
            _json_response(
                self,
                {
                    "incidents": [failure_incident("UNKNOWN", exc)],
                    "macro": {"vix": 0.0, "scan_timestamp": utc_timestamp()},
                },
                200,
            )
