# Aegis Codex — Doomsday Rapid Agent v2.0

**Autonomous geopolitical & financial risk intelligence platform**

Aegis Codex is an executive-level adversarial threat simulator built for the hackathon. It runs a multi-agent "Fracture Tribunal" that stress-tests company valuations against chaos scenarios — export controls, geopolitical flashpoints, supply chain shocks — and surfaces IC-ready memos with a human review gate before any model changes are applied.

The system runs autonomously: an hourly cron job scans your watchlist, auto-triggers tribunal debates for critical incidents, and has results waiting when you open the app. The only thing a portfolio manager needs to do is Approve, Soften, or Dismiss.

**Live demo:** deploy your own instance via the Vercel button below or follow the quickstart.

---

## Architecture

```
index.html          — single-page frontend (no framework, pure JS)
api/
  watchtower.py     — scans tickers via yfinance + Tavily, computes chaos index
  tribunal.py       — runs adversarial Bear / Bull / Judge LLM debate
  valuation.py      — multi-factor DCF + EV/Revenue distressed valuation
  codex_patch.py    — generates Python stress module stub via OpenAI
lib/
  agent_swarm.py    — orchestrates the Fracture Tribunal swarm (Nvidia NIM / OpenAI)
  risk_engine.py    — chaos index, severity classification, keyword scoring
  valuation_engine.py — WACC degradation, revenue haircuts, scenario matrix
  portfolio_manager.py — ticker validation, sector mapping
  arize_mcp_client.py  — OTLP trace export to Arize Phoenix
```

Deployed as Vercel serverless functions (Python 3.12). The frontend is a static HTML file served directly. No database — scan results and pre-run tribunal debates are cached in `/tmp` between invocations.

---

## Quickstart — local development

### Prerequisites

- Node.js (for Vercel CLI)
- Python 3.12
- At minimum one LLM API key (Nvidia NIM or OpenAI)

### 1. Clone

```bash
git clone https://github.com/mugichan-5627/Aegis_Codex.git
cd Aegis_Codex
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Set environment variables

Create a `.env` file in the project root:

```env
# Required — pick one LLM provider
NVIDIA_API_KEY=your_nvidia_nim_key

# Optional — enables live news search (falls back to keyword scoring without it)
TAVILY_API_KEY=your_tavily_key

# Optional — enables Arize Phoenix telemetry tracing
PHOENIX_API_KEY=your_phoenix_key
PHOENIX_COLLECTOR_ENDPOINT=https://app.phoenix.arize.com/v1/traces

# Optional — enables AI-generated code stubs in the Codex tab
OPENAI_API_KEY=your_openai_key
```

The app runs without any keys — it falls back to hardcoded demo data for all LLM calls.

### 4. Install Vercel CLI and run locally

```bash
npm install -g vercel
vercel dev
```

Opens at `http://localhost:3000`. This runs the Python serverless functions exactly as Vercel does in production — what you test is what gets deployed.

---

## Deploy to Vercel

### Option A — connect your GitHub repo

1. Go to [vercel.com](https://vercel.com) → New Project → import `mugichan-5627/Aegis_Codex`
2. Framework preset: **Other**
3. Add your environment variables under Settings → Environment Variables
4. Deploy

### Option B — Vercel CLI

```bash
vercel deploy --prod
```

---

## Environment variables reference

| Variable | Required | Purpose |
|---|---|---|
| `NVIDIA_API_KEY` | Recommended | Powers the Fracture Tribunal LLM debate (Llama 3.3 70B via Nvidia NIM) |
| `OPENAI_API_KEY` | Optional | Generates Python code stubs in the Codex tab |
| `TAVILY_API_KEY` | Optional | Live news search for risk keyword scoring |
| `PHOENIX_API_KEY` | Optional | Arize Phoenix cloud telemetry |
| `PHOENIX_COLLECTOR_ENDPOINT` | Optional | OTLP endpoint for Arize (defaults to Phoenix SaaS) |

---

## How it works

### Autonomous operation

Aegis runs an hourly cron job (`vercel.json`) that:
1. Scans the default watchlist via `GET /api/watchtower`
2. Caches results to `/tmp/aegis_last_scan.json`
3. Auto-triggers a tribunal debate for the first critical incident found
4. Caches the pre-run debate to `/tmp/aegis_last_tribunal.json`

When a user opens the app, incidents are already rendered and a red alert banner appears if any chaos index exceeds 0.7. The tribunal debate has already run — the user only needs to review the verdict.

### User flow

1. **Watchtower** — view live or cached scan results. Import your portfolio via text input (`AAPL, MSFT`) or upload a CSV file (first column = ticker). Click Scan Watchlist to run a fresh scan.
2. **Tribunal** — click any incident to load it, then Launch Tribunal. Bear, Bull, and Black Swan Judge agents debate the scenario in real time.
3. **Verdict** — review the IC memo, valuation waterfall, and scenario matrix. The Human Review Gate pauses the system — Approve, Soften (−15%), or Dismiss.
4. **Codex** — generate a Python stress module stub for the valuation engine based on the active scenario.
5. **Threat Orbit** — animated radar map showing all watchlist tickers orbiting a threat core, sized by threat score.
6. **Arize Telemetry** — live OTLP trace explorer showing every span from watchtower scans and tribunal runs.

### Portfolio import

- **Text input**: comma or space-separated tickers, e.g. `NVDA, TSM, ASML`
- **CSV upload**: upload a `.csv` file where the first column contains ticker symbols. An optional second column can hold portfolio weights (0–1) or share counts — Aegis uses tickers only for scanning. Header row is auto-detected and skipped. Supports up to 50 tickers.

**Example CSV format:**
```csv
ticker,weight
NVDA,0.30
TSM,0.25
AAPL,0.20
MSFT,0.15
RELIANCE.NS,0.10
```

Hover the **ⓘ** button next to the CSV upload in the app for a quick format reminder.

---

## Partner integrations

- **Nvidia NIM** — Llama 3.3 70B Instruct for the Fracture Tribunal debate
- **Arize Phoenix** — OTLP telemetry tracing for every agent span
- **Tavily** — live news search grounding for risk keyword scoring
- **yfinance** — real-time price data and drawdown calculation

---

*Built for the hackathon. Human oversight is a first-class feature, not an afterthought.*
