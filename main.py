"""
main.py — FastAPI server for the company research tool.

Endpoints:
  POST /api/research          { "company": "Apple" }  → { "job_id": "..." }
  GET  /api/stream/{job_id}   Server-Sent Events stream (progress updates)
  GET  /api/download/{job_id} Returns the finished .docx file
  GET  /                      Serves the frontend HTML
"""

import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from report import generate_report
from research import run_research

load_dotenv()

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Company Research Tool")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory job store ───────────────────────────────────────────────────
# Each job: { status, progress_pct, message, file_path, error, queue }
JOBS: dict[str, dict] = {}


# ─── Request / response models ─────────────────────────────────────────────
class ResearchRequest(BaseModel):
    company: str


class ResearchResponse(BaseModel):
    job_id: str


# ─── Background worker ─────────────────────────────────────────────────────
def _do_research(job_id: str, company: str):
    job = JOBS[job_id]

    def progress(message: str, pct: int):
        job["message"]      = message
        job["progress_pct"] = pct
        # Push event to the SSE queue
        job["queue"].put({"type": "progress", "message": message, "pct": pct})

    try:
        # Step 1: Research
        data = run_research(company, progress_callback=progress)

        # Step 2: Generate report
        progress("Building Word report...", 92)
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in company)
        file_path = OUTPUT_DIR / f"{safe_name}_{job_id[:8]}.docx"
        generate_report(data, str(file_path))

        job["status"]    = "complete"
        job["file_path"] = str(file_path)
        job["company"]   = data.get("company_name", company)
        job["score"]     = data.get("overall_score", 0)
        job["label"]     = data.get("overall_label", "")

        progress("Report ready!", 100)
        job["queue"].put({
            "type":         "complete",
            "download_url": f"/api/download/{job_id}",
            "company":      job["company"],
            "score":        job["score"],
            "label":        job["label"],
        })

    except Exception as e:
        job["status"] = "error"
        job["error"]  = str(e)
        job["queue"].put({"type": "error", "message": str(e)})


# ─── Endpoints ─────────────────────────────────────────────────────────────
@app.post("/api/research", response_model=ResearchResponse)
async def start_research(req: ResearchRequest):
    if not req.company.strip():
        raise HTTPException(400, "Company name is required.")

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status":       "running",
        "progress_pct": 0,
        "message":      "Starting...",
        "file_path":    None,
        "error":        None,
        "company":      req.company,
        "queue":        queue.Queue(),
    }

    thread = threading.Thread(
        target=_do_research,
        args=(job_id, req.company.strip()),
        daemon=True
    )
    thread.start()

    return ResearchResponse(job_id=job_id)


@app.get("/api/stream/{job_id}")
async def stream_progress(job_id: str):
    """Server-Sent Events stream for real-time progress updates."""
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found.")

    job = JOBS[job_id]

    def event_generator():
        # Stream existing progress first
        initial = json.dumps({"type": "progress", "message": job["message"], "pct": job["progress_pct"]})
        yield f"data: {initial}\n\n"

        while True:
            try:
                event = job["queue"].get(timeout=60)
                yield f"data: {json.dumps(event)}\n\n"

                if event["type"] in ("complete", "error"):
                    break
            except queue.Empty:
                # Keep-alive ping
                yield "data: {\"type\": \"ping\"}\n\n"

            if job["status"] in ("complete", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/download/{job_id}")
async def download_report(job_id: str):
    """Download the finished .docx report."""
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found.")

    job = JOBS[job_id]

    if job["status"] == "error":
        raise HTTPException(500, f"Research failed: {job['error']}")

    if job["status"] != "complete" or not job.get("file_path"):
        raise HTTPException(202, "Report not ready yet.")

    file_path = Path(job["file_path"])
    if not file_path.exists():
        raise HTTPException(404, "Report file not found.")

    company  = job.get("company", "Company")
    filename = f"{company} Research Report.docx"

    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """Polling fallback for environments where SSE doesn't work."""
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found.")
    job = JOBS[job_id]
    return {
        "status":       job["status"],
        "progress_pct": job["progress_pct"],
        "message":      job["message"],
        "error":        job.get("error"),
        "download_url": f"/api/download/{job_id}" if job["status"] == "complete" else None,
    }


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend not found. Place index.html in static/</h1>", status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
