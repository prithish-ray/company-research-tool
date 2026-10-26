"""
research.py — Orchestrates the company research workflow using Groq (llama-3.3-70b) + Tavily.

Runs an agentic loop: the model decides which searches to run, gathers evidence,
answers all research questions, scores the company, and returns structured JSON.
"""

import json
import os
import re
from typing import Callable

import httpx
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# ─── Research questions ────────────────────────────────────────────────────
RESEARCH_QUESTIONS = """
TENET 1 — DURABILITY

1.1 Strength and durability of moat
Does the company possess a strong and durable competitive moat (e.g., scale, network effects,
switching costs, brand, data, distribution, regulation) that is hard to copy and slow to erode?
Is the moat likely to strengthen with scale and time, or does growth actually weaken the moat?

1.2 Industry structure
Is the industry structure favourable for long-term value creation (limited number of strong
players, rational competition, structurally weak/fragile competitors), or is it inherently
cut-throat and commoditised?

1.3 Revenue recurrence and predictability
How recurring and predictable are the company's revenues (contracted, habitual, or utility-like),
and does this materially reduce business and earnings volatility?

1.4 Pricing power vs customers
Does the company have genuine pricing power with customers (ability to raise prices without
material volume loss), or is it largely a price-taker?
1.4.1 How mission-critical is the product or service to customers, and does that translate into
stickiness and pricing resilience?
1.4.2 Does the company offer high customer surplus and strong value-to-price, increasing the odds
that customers stick with it even under stress?

1.5 Pricing power vs suppliers
Does the company have healthy bargaining power versus suppliers (no critical input concentration
or hostage-like dependence), or is it structurally at risk from input price moves or disruptions?

1.6 Market leadership and strengthening brand
Does the company enjoy clear market leadership and/or strong brand positioning in its key
markets, and is that position strengthening?

1.7 Counter-positioning advantage
Does the company benefit from counter-positioning, where incumbents would struggle to copy its
model without damaging their legacy economics?

1.8 Customer surplus / value-for-money
Does the company offer high customer surplus and strong value-to-price, increasing the odds that
customers stick with it even under stress?

TENET 2 — COMPOUNDING CAPABILITY

2.1 Asset-light, scalable model
Is the business model genuinely asset-light and scalable, with low incremental capital required
per unit of additional revenue or gross profit?

2.2 Growth/reinvestment runway
Does the company have a long, credible growth runway (TAM, adjacencies, geography), or is it
already close to saturation? Is there clear evidence of a repeatable growth engine?

2.3 Repeatable growth engine
Is there clear evidence of a repeatable growth engine (e.g., successful replication into new
geographies, segments, or products; effective upsell and cross-sell) rather than one-off spikes?

TENET 3 — FRAGILITY

3.1 Obsolescence / disruption risk
How exposed is the business to technological, regulatory, or behavioural disruption, and is
there convincing evidence that its core offering is resilient?

3.2 Regulatory / political risk
How significant are the regulatory and political risks to the business model?

3.3 Cyclicality/defensiveness
How cyclical is the business across economic and industry cycles, and does its behaviour in past
downturns support a view of defensiveness or even antifragility?

3.4 Customer concentration risk
Is customer concentration low or clearly manageable?

3.5 Supplier concentration risk
Is supplier concentration low and free of single-point-of-failure risks?

3.6 Exposure to macro-sensitive demand
To what extent are the company's revenues tied to cyclical drivers such as GDP, marketing
budgets, capex, or employment cycles?
"""

SYSTEM_PROMPT = f"""You are a rigorous investment analyst performing a quality assessment of a company.

Your job is to research the company thoroughly using web searches, then answer a structured set
of research questions and produce a scored quality assessment.

## Research questions you must answer

{RESEARCH_QUESTIONS}

## Scoring rubric

Score each question 1–10:
- 9–10: Exceptional — clear, durable edge with minimal structural risk
- 7–8:  High quality — strong on most dimensions, minor concerns
- 5–6:  Average — meaningful strengths but material risks or uncertainty
- 3–4:  Below average — moat is weak or fragility is high
- 1–2:  Poor — commoditised, structurally impaired, or thesis-breaking risk

For Fragility questions (3.x): 10 = LEAST fragile (most resilient). Score 9-10 means very low risk.

## Tenet scoring

After answering all questions, assign a tenet score (1–10) for:
- Durability: weighted average of 1.1–1.8 answers
- Compounding Capability: weighted average of 2.1–2.3 answers
- Fragility: weighted average of 3.1–3.6 answers (higher = less fragile)

Overall Quality Score = (Durability × 0.40) + (Compounding × 0.35) + (Fragility × 0.25)

## Instructions

1. Use the web_search tool to gather evidence. Search for:
   - Annual reports, investor presentations, earnings calls
   - Competitive landscape, market share, industry structure
   - Revenue history, free cash flow, capital returns
   - Key risks: disruption, regulation, cyclicality, supplier/customer concentration
   - Analyst commentary and news

2. Do 8–12 targeted searches to build a strong evidence base before writing answers.

3. Answer every question with 2–5 sentences of specific, evidence-based analysis.
   Cite sources inline (e.g., "per the 2024 annual report").
   Flag gaps honestly where evidence is thin.

4. When finished researching and writing all answers, output ONLY valid JSON in this exact format,
   wrapped in ```json ... ``` markers:

{{
  "company_name": "Full legal/trading name",
  "description": "One sentence: what the company does",
  "research_date": "YYYY-MM-DD",
  "executive_summary": "3-5 sentence overview of the company and overall quality",
  "key_findings": [
    "Finding 1 (strongest positive)",
    "Finding 2",
    "Finding 3 (most important risk)",
    "Finding 4",
    "Finding 5"
  ],
  "questions": [
    {{
      "id": "1.1",
      "tenet": "Durability",
      "sub_tenet": "Moat Strength",
      "question": "Short question label",
      "answer": "Full 2-5 sentence evidence-based answer with citations",
      "judgement": "Strong | Mixed-Strong | Mixed | Weak-Mixed | Weak",
      "score": 7
    }}
  ],
  "tenet_scores": {{
    "durability":  {{"score": 7, "rationale": "2-3 sentence summary"}},
    "compounding": {{"score": 8, "rationale": "2-3 sentence summary"}},
    "fragility":   {{"score": 6, "rationale": "2-3 sentence summary"}}
  }},
  "overall_score": 7.1,
  "overall_label": "High Quality",
  "investment_thesis": "3-4 sentence plain-language investment thesis",
  "key_risks": ["Risk 1", "Risk 2", "Risk 3", "Risk 4"],
  "conviction": "Low | Medium | High",
  "conviction_rationale": "What evidence is missing that prevents higher conviction",
  "sources": [
    {{"title": "Source title", "url": "https://..."}}
  ]
}}

Questions array must include ALL 14 questions: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8,
2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6

IMPORTANT: Output ONLY the JSON block when you are done. No text after the closing ``` marker.
"""

# ─── Tool definition for Groq ──────────────────────────────────────────────
GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for information about the company. "
                "Use targeted queries to find annual reports, investor presentations, "
                "competitive analysis, financial data, and news."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific — include the company name and topic."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 10)"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# ─── Tavily search ─────────────────────────────────────────────────────────
def tavily_search(query: str, max_results: int = 5) -> str:
    """Run a search via Tavily and return formatted results."""
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "max_results": min(int(max_results), 10),
                "search_depth": "basic",
                "include_answer": True,
                "include_raw_content": False,
            },
            timeout=20.0
        )
        resp.raise_for_status()
        data = resp.json()

        parts = []
        if data.get("answer"):
            parts.append(f"Summary: {data['answer']}\n")
        for i, r in enumerate(data.get("results", []), 1):
            parts.append(
                f"[{i}] {r.get('title', 'No title')}\n"
                f"URL: {r.get('url', '')}\n"
                f"{r.get('content', '')[:800]}\n"
            )
        return "\n".join(parts) if parts else "No results found."

    except Exception as e:
        return f"Search error: {str(e)}"


# ─── Main research function ────────────────────────────────────────────────
def run_research(
    company_name: str,
    progress_callback: Callable[[str, int], None] | None = None
) -> dict:
    """
    Research a company using Groq (meta-llama/llama-prompt-guard-2-86m) + Tavily.

    progress_callback(message, pct) is called at each stage.
    Returns the research data as a dict.
    """

    def progress(msg: str, pct: int):
        if progress_callback:
            progress_callback(msg, pct)

    progress(f"Starting research on {company_name}...", 5)

    client = Groq(api_key=GROQ_API_KEY)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": f"Please research this company and produce a full investment quality assessment: {company_name}"}
    ]

    search_count   = 0
    MAX_SEARCHES   = 20
    MAX_ITERATIONS = 35

    progress("Searching for company overview and financials...", 10)

    STAGE_LABELS = {
        1:  "Searching for company overview...",
        2:  "Finding annual reports and financials...",
        3:  "Researching competitive position...",
        4:  "Analysing industry structure...",
        5:  "Evaluating pricing power and moat...",
        6:  "Assessing growth runway...",
        7:  "Investigating fragility and risks...",
        8:  "Checking cyclicality and macro exposure...",
        9:  "Reviewing supplier and customer dynamics...",
        10: "Gathering additional evidence...",
    }

    for _ in range(MAX_ITERATIONS):

        response = client.chat.completions.create(
            model="meta-llama/llama-prompt-guard-2-86m",
            messages=messages,
            tools=GROQ_TOOLS,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=15000,
        )

        message = response.choices[0].message

        # ── No tool calls → model is done; extract JSON ───────────────────
        if not message.tool_calls:
            full_text = message.content or ""
            match = re.search(r"```json\s*(.*?)\s*```", full_text, re.DOTALL)
            if match:
                progress("Parsing research results...", 90)
                return json.loads(match.group(1))

            # Sometimes the model omits fences — try parsing the whole text
            try:
                return json.loads(full_text.strip())
            except json.JSONDecodeError:
                raise ValueError(
                    "Model finished but no valid JSON found in response. "
                    f"Response preview: {full_text[:300]}"
                )

        # ── Append assistant message with tool calls ──────────────────────
        messages.append({
            "role":       "assistant",
            "content":    message.content,
            "tool_calls": [
                {
                    "id":       tc.id,
                    "type":     "function",
                    "function": {
                        "name":      tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in message.tool_calls
            ]
        })

        # ── Execute each tool call and append results ─────────────────────
        for tc in message.tool_calls:
            search_count += 1
            try:
                args      = json.loads(tc.function.arguments)
                query     = args.get("query", "")
                max_r     = int(args.get("max_results", 5))
            except (json.JSONDecodeError, ValueError):
                query = tc.function.arguments
                max_r = 5

            pct   = min(10 + search_count * 7, 85)
            label = STAGE_LABELS.get(search_count, f"Running search {search_count}...")
            progress(label, pct)

            if search_count > MAX_SEARCHES:
                result_content = "Search limit reached. Please synthesise from existing evidence."
            else:
                result_content = tavily_search(query, max_r)

            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      result_content,
            })

    raise TimeoutError(f"Research did not complete within {MAX_ITERATIONS} iterations.")
