# Company Research Tool

A web app that takes a company name and returns a full investment quality assessment as a Word document.

**What it does:** Searches the web, answers 14 structured research questions across three tenets (Durability, Compounding Capability, Fragility), scores the company out of 10, and delivers a formatted .docx report — all in 2–4 minutes.

---

## Quick Start (local)

### 1. Prerequisites

- Python 3.11+
- Two API keys (both free):
  - [Google AI Studio key](https://aistudio.google.com/app/apikey) — for Gemini 2.0 Flash (free: 1,500 req/day)
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

### 4. Run

```bash
uvicorn main:app --reload
```

Open http://localhost:8000 in your browser.

---

## Deploy to Railway (free, shareable link)

Railway gives you a public URL in about 5 minutes.

1. Push this folder to a GitHub repo
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your repo
4. In Railway → Variables, add:
   - `ANTHROPIC_API_KEY` = your key
   - `TAVILY_API_KEY` = your key
5. Railway auto-detects Python and deploys. Your app gets a public URL.

That's it — share the URL with anyone.

---

## Deploy to Render (alternative)

1. Push to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables (same as above)
6. Deploy

---

## Project structure

```
research-web-app/
├── main.py          # FastAPI server — endpoints, background jobs, SSE
├── research.py      # Claude agentic loop + Tavily web search
├── report.py        # Word document generation (python-docx)
├── requirements.txt
├── .env.example
├── README.md
└── static/
    └── index.html   # Frontend (single HTML file, no build step)
```

## How it works

1. User submits a company name via the web UI
2. `main.py` starts a background job and returns a `job_id`
3. The browser opens a Server-Sent Events stream to receive live progress
4. `research.py` runs an agentic Claude loop:
   - Claude decides which web searches to run (via Tavily)
   - Gathers evidence across 8–12 searches
   - Answers all 14 research questions with citations
   - Outputs structured JSON with scores and analysis
5. `report.py` takes the JSON and generates a formatted .docx
6. The browser receives a `complete` event and shows a download button

## Customising the research questions

Edit the `RESEARCH_QUESTIONS` constant in `research.py`. The questions are embedded as plain text — just add, remove, or rewrite them and the AI adapts automatically.

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
| Gemini 2.0 Flash | **Free** (up to 1,500 runs/day on free tier) |
| Tavily | **Free** up to 1,000 searches/month |

Both services have paid tiers if you exceed free limits. At scale, Gemini 2.0 Flash costs ~$0.002/run.
