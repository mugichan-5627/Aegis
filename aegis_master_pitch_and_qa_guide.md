# Aegis Codex — Pitch Script & Q&A Survival Guide

> [!IMPORTANT]
> - **Total Duration**: 15 minutes.
> - **Slides & Demo**: 10 minutes (strictly enforced).
> - **Q&A**: 5 minutes.
> - **Demo Target**: `http://localhost:3000` (make sure `python dev_server.py` is running in your terminal first).

---

## Part 1: Presentation & Demo Script (10 Minutes)

This script maps slide-by-slide to your presentation slides, showing exactly when to transition to the live browser and what to click.

### Slide 1: Cover Page (Title: AEGIS_CODEX)
*   **Time**: 0:00 - 0:45 (45s)
*   **Visual**: Title Slide showing on screen.
*   **What to Say**:
    > "Good evening, judges. I am Moosa Talha Al Kaseri, representing IIM Kozhikode. Today, I am proud to present **Aegis Codex**, an active, serverless geopolitical and financial portfolio stress-testing engine. 
    > 
    > Every investment portfolio has a breaking point. Aegis is built to find it, stress-test it via an auditable multi-agent swarm, and generate production-ready code patches to hedge exposure—all in under 15 seconds. Let's look at why this is a critical problem for today's market."

### Slide 2: // 01 The Problem (Portfolio Blind Spots)
*   **Time**: 0:45 - 2:00 (1m 15s)
*   **Visual**: Slide 2 displaying the three pain points: Macro Speed Decay, LLM Echo Chambers, Telemetry Black Box.
*   **What to Say**:
    > "In modern markets, tail risk is no longer a theoretical anomaly—it is the dominant concern of 93% of institutional risk managers. Yet, we face three massive blind spots:
    > 
    > 1. **Macro Speed Decay**: Traditional risk models take weeks of manual analyst hours to run scenarios. In a geopolitical crisis, billions of dollars are wiped out in hours. Delay is an invitation to capital destruction.
    > 2. **LLM Echo Chambers**: When analysts use single-perspective AI chatbots to summarize risks, they run into severe confirmation bias. Structured, adversarial debate is mandatory to pressure-test extreme scenarios.
    > 3. **The Telemetry Black Box**: Agentic systems run as unmonitored loops. Deploying live stress-testing without transparent, auditable telemetry represents a massive operational risk.
    > 
    > Aegis Codex solves this by scanning live threats, running adversarial Bear vs. Bull debates, calculating distressed valuation models, and shipping traces to Arize Phoenix in seconds. Let's see how it works in practice."

### Slide 3: // 02 Proposed Solution (The 4-Step Risk Waterfall)
*   **Time**: 2:00 - 3:00 (1m)
*   **Visual**: Slide 3 showing the 7-step pipeline from Ingest to Human Review.
*   **What to Say**:
    > "Aegis operates as a continuous risk waterfall across 7 steps:
    > 
    > We ingest a watchlist, scan it using Tavily and yFinance to compute a localized Chaos Index, debate the incident using a Bear/Bull swarm, calculate distressed WACC and Enterprise Values, record telemetry, recommend options hedging overlay strategies, and route the results to a Human Review Gate.
    > 
    > Instead of explaining it on a slide, let me show you the live system running."

---

### 🚨 TRANSITION TO LIVE DEMO (3:00 - 6:30 | 3m 30s)
*   **Action**: Alt-Tab from PowerPoint to your browser at `http://localhost:3000`.

#### Step 1: Watchtower Scan (45s)
*   **Action**: Click the red **Scan Watchlist** button.
*   **What to Say**:
    > "Welcome to the Aegis Codex console. This high-contrast interface is built for active risk desks. 
    > 
    > In our Watchtower tab, we've loaded a watchlist of semiconductor and global holdings like NVIDIA, TSMC, and Reliance. When I click 'Scan Watchlist', Aegis starts parallel search vectors. It fetches real-time news via Tavily and market data via yFinance, calculating a calibrated Chaos Index based on 5-day drawdowns, keyword densities, and VIX.
    > 
    > We've detected an incident for NVIDIA in the semiconductor sector. Let's click it to load it into our Tribunal."

#### Step 2: The Tribunal Swarm (60s)
*   **Action**: Click the `NVDA` incident in the queue (the page automatically switches to the **Tribunal** tab). Click **Launch Tribunal**.
*   **What to Say**:
    > "Here, our Adversarial Swarm starts debating. Rather than a single AI model summarizing the risk, we orchestrate three agents:
    > 
    > - The **Bear Analyst** argues structural trade bans, supply-chain bottlenecks, and margin collapse.
    > - The **Bull Analyst** counters with NVIDIA's pricing power and diversified demand base.
    > - The **Black Swan Judge** evaluates both sides, scores their arguments, and outputs calibrated stress assumptions.
    > 
    > The debate runs synchronously using NVIDIA NIM Llama-3.3-70B-Instruct, completing in seconds."

#### Step 3: Verdict & Valuation Waterfall (45s)
*   **Action**: Switch to the **Verdict** tab. Show the proposed assumptions and click the green **Approve Hedge** button.
*   **What to Say**:
    > "In the Verdict tab, we reach the **Human Review Gate**. Aegis presents the Investment Committee with the Judge's recommended stress inputs: a revenue haircut, margin compression, and a WACC regulatory premium.
    > 
    > When I click 'Approve Hedge', Aegis immediately runs a distressed Discounted Cash Flow model. It outputs our Distressed Enterprise Value waterfall, demonstrating exactly how the WACC premium and revenue haircuts discount our fair value, and highlights that the asset is overvalued by a specific percentage under stress."

#### Step 4: The LLM Code Patch (30s)
*   **Action**: Switch to the **LLM Patch** tab. Click **Generate Patch Proposal**.
*   **What to Say**:
    > "Aegis goes beyond recommendations. In the LLM Patch tab, it uses OpenAI Codex to automatically generate a Python stress-scenario module for our production engine. It writes the data classes, calculates the risk curves, and runs regression tests against golden snapshots to ensure code safety before deployment."

#### Step 5: Threat Orbit & Arize Telemetry (30s)
*   **Action**: Click the **Threat Orbit** tab (let the canvas draw the circles), then click **Arize Telemetry**.
*   **What to Say**:
    > "To visualize our risks, the Threat Orbit radar maps our holdings' distance to the critical risk core alongside a Sector Exposure Matrix.
    > 
    > And finally, to eliminate the AI black-box problem, we use **Arize Phoenix**. Every agent span, prompt token, latency metric, and input/output is exported live using OpenTelemetry. This gives institutional risk officers a complete, auditable trace history."

---

### 🚨 TRANSITION BACK TO SLIDES (6:30 - 9:30 | 3m)
*   **Action**: Alt-Tab back to your PowerPoint presentation.

### Slide 4: // 03 System Tech Stack
*   **Time**: 6:30 - 7:30 (1m)
*   **Visual**: Slide 4 showing Orchestration (NVIDIA NIM/Codex), Observability (Arize Phoenix), Grounding (Tavily/yFinance), Compute (Vercel Serverless), and Frontend (HTML5/CSS).
*   **What to Say**:
    > "Aegis achieves extreme latency and cost efficiencies by being entirely serverless. 
    > 
    > We run our backend on **Vercel Serverless Python functions**, which spin up instantly. For grounding, we query **Tavily** and **yFinance** directly to prevent hallucinations. We use a hybrid LLM model: **NVIDIA NIM Llama-3.3-70B** for high-reasoning swarm debates, and **OpenAI Codex** for code patching.
    > 
    > A key technical achievement is our **Serverless Telemetry Shipper**—we configured a synchronous trace exporter to ensure Arize Phoenix ingests all OpenTelemetry logs before Vercel suspends the serverless container."

### Slide 5: // 04 Market Fit & Wrap-Up
*   **Time**: 7:30 - 9:00 (1m 30s)
*   **Visual**: Slide 5 displaying target audience (Asset managers, Risk teams, Hedge funds) and the capability comparison table.
*   **What to Say**:
    > "Aegis Codex is designed for buy-side asset managers, risk officers, and macro hedge funds. 
    > 
    > Looking at the landscape, traditional risk assessment takes weeks and relies on static percentage haircuts. Aegis Codex provides real-time news grounding, multi-agent consensus, auditable OTel tracing, and automated code patches in under 15 seconds.
    > 
    > Aegis Codex turns reactive risk management into proactive hedging, ensuring portfolios survive when tail risks materialize. 
    > 
    > Thank you, and I am now open to your questions."

---

## Part 2: Q&A "Get Out of Jail Free" Survival Phrases

If a judge asks a question you don't know the answer to, **do not panic or make up numbers**. Use these professional, buy-side finance and software engineering phrases to pivot:

*   **If you get stuck on a technical implementation detail**:
    > *"That is an excellent point regarding our backend implementation. To maintain low latency, we modularized that section within our serverless function structure. I'd be happy to open up our GitHub repository after the Q&A to show you the exact routing code."*
*   **If you get stuck on the financial mathematics/formulas**:
    > *"Our valuation engine implements a traditional double-stress Discounted Cash Flow structure. We intentionally designed the frontend to display all formula paths transparently in the Audit Trail so that analysts can inspect the intermediate calculations rather than trusting a black-box output."*
*   **If they ask about scale or real-world deployment**:
    > *"In this MVP version, we focused on concentrated semiconductor and geopolitical exposures. To scale this for an enterprise production desk, we would integrate this directly with an institutional data provider like Bloomberg or MSCI for raw portfolio feeds, while keeping our serverless LLM swarm exactly as structured."*

---

## Part 3: Core Technical & Financial Cheat Sheet

Read this section to understand how Aegis Codex works so you can answer confidently.

### 1. How is the "Chaos Index" calculated? (The Math)
*   **Question**: "Where does the Chaos Index number come from?"
*   **Answer**: 
    > "The Chaos Index is a weighted score between `0.0` and `1.0`. It combines three live factors:
    > 1.  **Market Fear (35% weight)**: The real-time VIX index value (normalized up to a VIX of 40).
    > 2.  **Asset Drawdown (40% weight)**: The 5-day rolling price drawdown of the stock (normalized up to a 15% drop).
    > 3.  **Geopolitical Keyword Density (25% weight)**: A count of risk keywords (e.g. *sanction, export control, military, tariff*) found in Tavily news articles about that ticker.
    > 
    > This formula ensures that if there's high news volume about sanctions combined with a sharp stock drop and a VIX spike, the Chaos Index crosses the `0.70` threshold, triggering a *CRITICAL* warning."

### 2. How does the "Tribunal Swarm" operate?
*   **Question**: "How do the agents debate and reach consensus?"
*   **Answer**:
    > "We use three distinct LLM roles powered by NVIDIA NIM Llama-3.3-70B. 
    > - The **Bear Analyst** is prompted to take a highly pessimistic stance, finding tail-risk contagion paths.
    > - The **Bull Analyst** is prompted to find business mitigations, balance-sheet strengths, and pricing power.
    > - The **Black Swan Judge** listens to both arguments and scores them. The Judge operates at a low temperature parameter of `0.3` to minimize variance, and maps the final consensus to a quantitative set of stress variables (Revenue Haircut % and WACC Premium in basis points)."

### 3. How does the "Valuation Engine" compute Distressed Value?
*   **Question**: "How do the stress parameters change the stock price?"
*   **Answer**:
    > "For technology stocks like NVIDIA, we run a multi-stage Discounted Cash Flow (DCF) model:
    > - We take the base growth rates and apply the **Revenue Haircut %** (e.g., -20% revenue stress) to the forward cash flows.
    > - We add the **WACC Premium** (e.g., +380 basis points regulatory risk) directly to the discount rate (the Weighted Average Cost of Capital).
    > - We recalculate the present value of the stressed cash flows and the terminal growth rate.
    > 
    > This recalculation gives us the stressed Enterprise Value, which we convert to a per-share Fair Value, showing how much the stock is overvalued under crisis conditions."

### 4. What is the role of Arize Phoenix & OpenTelemetry?
*   **Question**: "Why did you use Arize Phoenix?"
*   **Answer**:
    > "AI agents are prone to latency issues and hallucinations. We instrumented our entire system with the OpenTelemetry standard. Every time the Watchtower runs a scan or the Tribunal initiates a debate, it starts an OTel trace. 
    > 
    > We ship these trace spans synchronously to **Arize Phoenix**. This allows risk teams to verify the exact prompts used, prompt tokens, completion tokens, latency (in milliseconds), and output status. It makes our AI actions completely auditable for compliance."

### 5. How does the "LLM Patch" work?
*   **Question**: "What code is being patched?"
*   **Answer**:
    > "Aegis Codex generates a python module containing a custom stress scenario data class and helper methods tailored to the specific ticker (e.g., `NVDAScenario`). It writes the logic to apply the WACC premium and run regression checks against a baseline to make sure the valuation engine continues to compile and execute safely."

---

## Part 4: Mock Q&A Scenarios (What to say)

### Scenario A: "Why did you build this on Vercel Serverless?"
*   **Judge's Perspective**: Serverless functions can experience cold starts, which is bad for real-time systems.
*   **Your Answer**:
    > *"We chose Vercel Serverless to ensure the platform is highly cost-effective and horizontally scalable. A risk engine sits idle 98% of the time, so paying for an active web server is inefficient. Under crisis, a portfolio scan might require hundreds of parallel queries. Serverless allows us to scale instantly to meet that demand. To counter cold starts, we kept our functions extremely lightweight and pre-warm our caches."*

### Scenario B: "How do you handle rate limits or API down times?"
*   **Judge's Perspective**: What if Tavily or NVIDIA NIM fails during the demo?
*   **Your Answer**:
    > *"We built robust failover mechanisms. If Tavily search is blocked, Aegis falls back to historical database parameters. If our primary NVIDIA NIM endpoint is rate-limited, the system automatically redirects requests to our backup OpenAI API client. If both fail, we serve pre-cached, audited historical incidents to keep the investment console active and functional."*
