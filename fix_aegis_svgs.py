import os

dirs_to_update = [
    r"c:\Users\Moosa\Downloads\Aegis_Codex\ppt-master\projects\aegis_pitch_ppt169_20260601\svg_output",
    r"c:\Users\Moosa\Downloads\Aegis_Codex\ppt-master\projects\aegis_pitch_ppt169_20260601\svg_final"
]

replacements = {
    # Footers
    "PROJECT DOOMSDAY — CONFIDENTIAL": "AEGIS CODEX — PROPRIETARY & CONFIDENTIAL",
    "PROJECT DOOMSDAY — HACKATHON CONFIDENTIAL": "AEGIS CODEX — PROPRIETARY & CONFIDENTIAL",
    "DOOMSDAY RAPID AGENT PLATFORM v2.0": "ACTIVE GEOPOLITICAL PORTFOLIO STRESSING ENGINE",
    
    # Slide 1 metrics & tagline
    "COORDINATED AI AGENTS": "SWARM AGENTS",
    "5\n  </text>": "3\n  </text>", # Note: could be formatted differently in SVG
    "5</text>": "3</text>",
    "PARALLEL SEARCH VECTORS": "REAL-TIME API SCANS",
    "6\n  </text>": "12\n  </text>",
    "6</text>": "12</text>",
    "&lt; 60s": "LIVE",
    "&lt; 60s</text>": "LIVE</text>",
    "ANALYSIS RUNTIME": "ARIZE TRACING",
    "find it in 60s.\"": "expose it via debate.\"",
    "BUILT WITH: GEMINI 2.0 FLASH + NVIDIA NIM + TAVILY": "BUILT WITH: OPENAI CODEX | NVIDIA NIM | ARIZE PHOENIX",
    
    # Slide 2 Problem
    "NORMAL DISTRIBUTION FAILURE": "MACRO SPEED DECAY",
    "Traditional models assume Gaussian normal distribution returns. They collapse": "Traditional models take weeks to assess macro shocks. Geopolitical events compress",
    "precisely when tail risk materializes. 2008, COVID, and SVB were not outliers—": "asset values in hours. Delay is an invitation to capital destruction.",
    "they were fatal model blind spots.": "",
    
    "SILOED RISK IDENTIFICATION": "LLM ECHO CHAMBERS",
    "Analysts identify risk factors in isolation, missing second-order cascades": "Single-perspective AI risk summaries suffer from severe confirmation bias.",
    "and geographic convergence. Risk A triggering Risk B triggering Risk C": "Structured adversarial debate is mandatory to steel-manned extreme scenarios.",
    "remains entirely invisible to current tools.": "",
    
    "THE TOOLING GAP": "THE TELEMETRY BLACK BOX",
    "Existing tools are either too simplistic (flat percentage haircuts), too slow": "Most agentic architectures run as unmonitored loops. Deploying live",
    "(requiring weeks of manual scenario modelling), or operate as proprietary": "stress-testing without auditable telemetry is a major operational risk.",
    "black boxes with zero methodology transparency.": "",
    
    "93%\n  </text>": "93%\n  </text>",
    "OF INSTITUTIONAL INVESTORS CITE TAIL RISK AS #1 CONCERN": "OF FINANCIAL FIRMS CONCERNED ABOUT TAIL-RISK EXPOSURE",
    "YET ONLY 12% HAVE SYSTEMATIC TOOLS TO MODEL IT.": "YET FEW HAVE SYSTEMATIC TOOLS TO MODEL REAL-TIME CRISES",
    "— GLOBAL PORTFOLIO TAIL RISK SURVEY": "— INSTITUTIONAL RISK SURVEY 2026",
    
    # Slide 3 Solution
    "PROPOSED SOLUTION / 7-STEP PIPELINE": "PROPOSED SOLUTION & JOURNEY / 4-STEP WATERFALL",
    "02 · HOW IT WORKS: END-TO-END AUTONOMOUS ENGINE": "02 · THE END-TO-END RISK WATERFALL FLOW",
    "USER INPUT": "PORTFOLIO INGEST",
    "Ticker entry or CSV upload": "User imports asset watchlist",
    "with weight + Chaos (0-1).": "via CSV or text input.",
    
    "WORLD STATE": "WATCHTOWER SCAN",
    "Live metrics: VIX, Oil, Gold,": "Searches Tavily & yFinance",
    "Yields → Global Fear Class.": "to output localized Chaos Index.",
    
    "COMPANY PROFILE": "TRIBUNAL SWARM",
    "Smart ticker resolve via yfinance": "Bear & Bull Analysts debate",
    "and Auto USD normalisation.": "scenarios with Judge verdict.",
    
    "INTELLIGENCE SCAN": "VALUATION PATCH",
    "6 parallel Tavily vectors →": "Generates model stress patch",
    "Gemini synthesises 6 risks.": "and Investment Committee memo.",
    
    "PHASE 2: ANALYSIS & VALUATION": "PHASE 2: ADVERSARIAL ANALYSIS & HEDGING",
    "ADVERSARIAL TRIBUNAL DEBATE": "TELEMETRY RECORD",
    "Adversarial Bear (Prosecution) ⟷ Bull (Defence) ⟷ Judge (Verdict)": "Traces all prompt inputs, outputs,",
    "runs a 3-agent debate per risk to prevent confirmation bias.": "and span latencies live to Arize Phoenix.",
    
    "GEOGRAPHIC EXPOSURE MAPPING": "PORTFOLIO HEDGE",
    "Fracture nodes + curved convergence vectors plotted on interactive": "Executes option-hedging rules",
    "Plotly threat globe, pinpointing hot-spots in under 60 seconds.": "(protective puts) to preserve capital.",
    
    "VALUATION CASCADE & HUMAN GATE": "HUMAN REVIEW GATE",
    "Stressed valuation matrix (5 distinct paths). Traces credit/refinancing": "Investment Committee reviews",
    "contagion before prompting User Gate (Approve, Soften, Dismiss).": "and approves distressed WACC changes.",
    
    "5 AI AGENTS IN SWARM COORDINATION": "3 SWARM AGENTS · OPENAI CODEX + NVIDIA NIM ORCHESTRATION · ARIZE PHOENIX TELEMETRY",
    "Primary models: Google Gemini 2.0 Flash via Google AI Studio for fast JSON processing.": "Primary models: OpenAI Codex endpoint for code generation, Nvidia NIM Llama 3.3 70B for debates.",
    "Failover routing: NVIDIA NIM (Llama 3.3 70B Instruct) and Fireworks AI ensure zero rate-limit disruptions.": "Observability link: Synchronous OTel trace shipper logs agent steps directly to Arize Phoenix SaaS.",
    
    # Slide 4 Innovation
    "03 · 5 SPECIALIZED AGENTS IN COORDINATED SWARM": "03 · 3 SWARM AGENTS + HUMAN REVIEW + CODEX PATCHING",
    "INTELLIGENCE ANALYST": "BEAR ADVOCATE",
    "Temp: T = 0.5": "Temp: T = 0.6",
    "Synthesises 6 Tavily": "Argues worst-case scenario with",
    "vectors + company": "historical precedents &",
    "fundamentals into": "catastrophic framing. Pushes",
    "geolocated risk": "WACC premiums and revenue",
    "scenarios with severity,": "haircuts upwards. Acts as",
    "probability, and": "adversarial counterweight.",
    "revenue-at-risk\n  </text>": "",
    "estimates.": "",
    
    "BEAR ADVOCATE\n  </text>": "BULL ADVOCATE\n  </text>",
    "PROSECUTION": "DEFENCE",
    "Temp: T = 0.6": "Temp: T = 0.6",
    "Argues worst-case with": "Challenges evidence, presents",
    "historical precedents": "mitigating factors, and argues",
    "and catastrophic": "the market has already priced",
    "framing. Pushes": "the risk in. Pushes severity",
    "severity metrics up.": "metrics downwards.",
    "Acts as adversarial": "",
    "counterweight to the": "",
    "bull analyst.": "",
    
    "BULL ADVOCATE\n  </text>": "FRACTURE JUDGE\n  </text>",
    "DEFENCE": "VERDICT",
    "Temp: T = 0.6": "Temp: T = 0.3",
    "Challenges evidence,": "Low-temperature, high-conviction",
    "presents mitigating": "arbiter. Computes final severity",
    "factors, and argues": "score and extracts proposed",
    "the market has already": "stress assumptions (revenue haircut,",
    "priced the risk in.": "margin compression, WACC premium).",
    "Pushes severity metrics": "",
    "downwards.": "",
    
    "FRACTURE JUDGE\n  </text>": "HUMAN REVIEW GATE\n  </text>",
    "FINAL VERDICT": "EXECUTIVE GATE",
    "Temp: T = 0.3": "PM OVERRIDE",
    "Low-temperature,": "Pauses automation for executive",
    "high-conviction arbiter.": "override. PM reviews the tribunal's",
    "Uses calibrated rubric:": "consensus and selects Approve,",
    "8+ is catastrophic,": "Soften (-15%), or Dismiss",
    "6–7 is material,": "to adjust valuations.",
    "<4 is dismissed.": "",
    "Acts as final authority.": "",
    
    "CONTAGION MODELER": "CODEX MODEL PATCHING",
    "Temp: T = 0.5": "CODE GENERATION",
    "Models 2nd, 3rd, and": "Auto-generates a Python stress",
    "4th-order propagation.": "module subclass stub via OpenAI",
    "Traces how a shock": "Codex to dynamically inject",
    "cascades through": "stress variables into the",
    "corporate P&L → credit": "valuation engine code.",
    "ratings → refinancing": "",
    "costs → capital expenditure.": "",
    
    # Slide 5 Tech Stack
    "04 · TECHNOLOGY SELECTION & RESILIENT DEPLOYMENT": "04 · ORCHESTRATION, OBSERVABILITY & COMPUTE STACK",
    "PRIMARY COGNITION": "ORCHESTRATION",
    "Google Gemini 2.0 Flash": "OpenAI Codex + Nvidia NIM",
    "● Low-latency structured JSON output": "● Primary Codex endpoint for model patch code",
    "● Connected directly via Google AI Studio": "● Failover to Nvidia NIM Llama 3.3 70B for debates",
    
    "FAILOVER COGNITION": "OBSERVABILITY",
    "NVIDIA NIM (Llama 3.3 70B)": "Arize Phoenix (OTel)",
    "● Auto-switch rate limit mitigation": "● Logs spans, inputs, & prompt token counts",
    "● High capacity tribunal failover hosting": "● Synchronous trace shipper for serverless dev",
    
    "REAL-TIME RESEARCH": "DATA GROUNDING",
    "Tavily Search API": "Tavily Search + yFinance",
    "● Grounds intelligence vectors in live events": "● Live geopolitical news feeds avoid hallucination",
    "● Prevents stale hallucinations in tribunal": "● yFinance pulls quotes & historical drawdowns",
    
    "MARKET TELEMETRY": "COMPUTE STACK",
    "yfinance Data Feed": "Vercel Serverless",
    "● Live quotes, fundamentals, FX matrices": "● REST APIs run on serverless python functions",
    "● Covers over 60 global stock exchanges": "● Low latency executions without persistent VM",
    
    "PRESENTATION LAYER": "FRONTEND LAYER",
    "Streamlit / Static HTML": "HTML5 / Vanilla CSS",
    "● Single-file python rapid UI layout": "● High contrast dark dashboard dashboard",
    "● High fidelity threat radar Plotly maps": "● Collapsing trace tree explorer & radar canvas",
    
    "VISUAL DATA RENDERING": "OBSERVABILITY",
    "Plotly Engine": "Arize Phoenix",
    "● Geolocated curved threat charts": "● Spans, token parameters, & prompt counts",
    "● Transparent waterfall valuation graphs": "● Direct OTLP trace files exported to SaaS link",
    
    "Instrumented with Arize Phoenix open telemetry tracing. Every agent span, Tavily search vector,": "▸ Serverless telemetry: Synchronous trace shipper ensures OTel data ingestion before lambda container suspension",
    "and LLM judge decision exports OTLP trace files to cloud endpoints for monitoring, tracking latency and cost.": "▸ Grounded AI: Every agent output is anchored in live financial metrics and real-time news search results",
    
    # Slide 6 Roadmap
    "05 · NEXT 3 TO 6 MONTHS PRODUCT DEVELOPMENT SCHEDULE": "05 · PRODUCT DEPLOYMENT & MILESTONES ROADMAP",
    "SEC 10-K PARSING": "SEC EDGAR PARSING",
    "● Auto-parse Item 1A": "● Auto-parse Item 1A 10-K",
    "  filing risk sections": "  sections for baseline risks",
    "SEBI / BSE FEED": "SEBI / BSE FILINGS",
    "● Support Indian equities": "● SEBI filings integration",
    "● Deep regulatory scans": "  for Indian listed equities",
    "PORTFOLIO ENGINE": "PORTFOLIO & PDF",
    "● Cross-holding correlations": "● Cross-ticker correlations",
    "● McKinsey-style PDF reports": "● McKinsey-style PDF reports",
    "LYING GAP / WEBHOOK": "LYING GAP & WEBHOOK",
    "● News vs filing divergence": "● News vs filing divergence",
    "● Slack/Teams alarms": "● Teams & Slack alerts",
    
    # Slide 7 GTM
    "PLATFORM UNIT ECONOMICS": "AEGIS PLATFORM UNIT ECONOMICS",
    "Gemini API Cost / Analysis": "OpenAI / NVIDIA API Cost",
    "Tavily Search Cost / Analysis": "Tavily Search Cost",
    
    # Slide 9 Conclusion
    "MILAN AI WEEK HACKATHON 2026 // SYSTEM TERMINUS": "OPENAI × OUTSKILL HACKATHON 2026 // SYSTEM TERMINUS",
}

for d in dirs_to_update:
    print(f"\nProcessing directory: {d}")
    for f_name in sorted(os.listdir(d)):
        if f_name.endswith('.svg'):
            f_path = os.path.join(d, f_name)
            with open(f_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            orig_content = content
            for old, new in replacements.items():
                content = content.replace(old, new)
            
            if content != orig_content:
                with open(f_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  Updated: {f_name}")
            else:
                print(f"  No changes for: {f_name}")

print("\nSVG files replacement finished.")
