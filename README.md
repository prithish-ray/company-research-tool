# Company Research Tool

A web app that takes a company name and returns a full investment quality assessment as a Word document.

**What it does:** Searches the web, answers 14 structured research questions across three tenets (Durability, Compounding Capability, Fragility), scores the company out of 10, and delivers a formatted .docx report — all in 2–4 minutes.

---

## Quick Start (local)

### 1. Prerequisites

- Python 3.11+
- Two API keys (both free):
  - [Groq API key](https://console.groq.com) — for Llama 3.3 70b (free tier, no card required)
  - [Tavily API key](https://app.tavily.com) — for web search (free: 1,000 searches/month)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Then edit .env and add your API keys
```

Your `.env` should look like this:

```
GROQ_API_KEY=gsk_...
TAVILY_API_KEY=tvly-...
OUTPUT_DIR=./outputs
```

### 4. Run

```bash
uvicorn main:app --reload
```

Open http://localhost:8000 in your browser.

---

## Deploy to Render (recommended)

Render gives you a public, shareable URL in about 5 minutes.

1. Push this folder to a GitHub repo (make sure `.env` is in `.gitignore`)
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `/opt/render/project/src/.venv/bin/uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Go to the **Environment** tab and add:
   - `GROQ_API_KEY` = your key
   - `TAVILY_API_KEY` = your key
6. Deploy — your app gets a public URL to share with anyone

> **Note:** Render's free tier spins down after 15 minutes of inactivity. The first request after idle takes ~30 seconds to wake up. Upgrade to a paid instance ($7/month) to keep it always-on.

---

## Project structure

```
research-web-app/
├── main.py          # FastAPI server — endpoints, background jobs, SSE
├── research.py      # Groq agentic loop + Tavily web search
├── report.py        # Word document generation (python-docx)
├── requirements.txt
├── runtime.txt      # Pins Python 3.11 for Render
├── .env.example
├── README.md
└── static/
    └── index.html   # Frontend (single HTML file, mobile-responsive, no build step)
```

## How it works

1. User submits a company name via the web UI
2. `main.py` starts a background job and returns a `job_id`
3. The browser opens a Server-Sent Events stream to receive live progress
4. `research.py` runs an agentic loop using Groq (Llama 3.3 70b):
   - The model decides which web searches to run (via Tavily)
   - Gathers evidence across 8–12 searches
   - Answers all 14 research questions with citations
   - Outputs structured JSON with scores and analysis
5. `report.py` takes the JSON and generates a formatted .docx
6. The browser receives a `complete` event and shows a download button

## Research framework

The tool evaluates companies across three tenets:

| Tenet | Weight | Questions |
|-------|--------|-----------|
| Durability (moat strength) | 40% | 1.1 – 1.8 |
| Compounding Capability | 35% | 2.1 – 2.3 |
| Fragility (10 = least fragile) | 25% | 3.1 – 3.6 |

Overall Quality Score = (Durability × 0.40) + (Compounding × 0.35) + (Fragility × 0.25)

## Customising the research questions

Edit the `RESEARCH_QUESTIONS` constant in `research.py`. The questions are embedded as plain text — just add, remove, or rewrite them and the model adapts automatically.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/research` | Start a research job. Body: `{"company": "Apple"}`. Returns `{"job_id": "..."}` |
| GET | `/api/stream/{job_id}` | SSE stream of progress events |
| GET | `/api/status/{job_id}` | Polling fallback — returns current status JSON |
| GET | `/api/download/{job_id}` | Download the finished .docx |
| GET | `/` | Serves the frontend |

## Estimated costs per research run

| Service | Cost |
|---------|------|
| Groq (Llama 3.3 70b) | **Free** on the free tier |
| Tavily | **Free** up to 1,000 searches/month |

Both services have paid tiers if you exceed free limits.
