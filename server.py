"""
FastAPI backend for the Instagram Discovery Dashboard.
Runs on http://localhost:8000

Start: uvicorn server:app --reload --port 8000
"""

import io
import csv
import uuid
import logging
import threading
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

import config
from api_client import InstagramClient, InstagramAPIError
from discovery import DiscoveryEngine
from database import (
    init_db,
    get_top_creators,
    get_creators_by_status,
    update_creator_status,
    query_creators,
    get_queue_for_date,
    fill_queue_for_date,
    get_posts_for_creator,
    mark_queue_item,
    get_queue_stats,
)
from suggestions import build_action_plan


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Instagram Discovery Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

client = InstagramClient(config.ACCESS_TOKEN, config.IG_USER_ID)
engine = DiscoveryEngine(client)

# ---------------------------------------------------------------------------
# Discovery run state (in-memory)
# ---------------------------------------------------------------------------

_run_lock = threading.Lock()
run_state: dict = {
    "status":        "idle",   # idle | running | done | error
    "run_id":        None,
    "log_lines":     [],
    "started_at":    None,
    "finished_at":   None,
    "results_count": 0,
}


class _SSELogHandler(logging.Handler):
    """Appends log records to run_state['log_lines'] during a discovery run."""
    def emit(self, record: logging.LogRecord) -> None:
        with _run_lock:
            if run_state["status"] == "running":
                run_state["log_lines"].append(self.format(record))


_sse_handler = _SSELogHandler()
_sse_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", "%H:%M:%S"))
logging.getLogger().addHandler(_sse_handler)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class DiscoveryRunRequest(BaseModel):
    hashtags:    Optional[list[str]] = None
    mode:        str = "top"
    media_limit: int = 50


class StatusUpdateRequest(BaseModel):
    status: str
    notes:  str = ""


# ---------------------------------------------------------------------------
# Account endpoints
# ---------------------------------------------------------------------------

@app.get("/api/account/stats")
def account_stats():
    try:
        profile = client.get_my_profile()
        rate    = client.rate_status()
        return {**profile, **rate}
    except InstagramAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Leads endpoints
# ---------------------------------------------------------------------------

@app.get("/api/leads")
def leads(
    status:  str = "",
    niche:   str = "",
    sort_by: str = "score",
    order:   str = "desc",
    limit:   int = 100,
    offset:  int = 0,
):
    allowed_sorts = {"score", "followers", "engagement_rate", "discovered_at", "username"}
    if sort_by not in allowed_sorts:
        sort_by = "score"
    if order not in ("asc", "desc"):
        order = "desc"
    limit  = min(max(limit, 1), 500)
    offset = max(offset, 0)

    items, total = query_creators(
        status=status, niche=niche,
        sort_by=sort_by, order=order,
        limit=limit, offset=offset,
    )
    return {"total": total, "items": items}


@app.patch("/api/leads/{creator_id}/status")
def update_lead_status(creator_id: str, body: StatusUpdateRequest):
    allowed = {"new", "reviewed", "contacted", "skip"}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of {allowed}")
    update_creator_status(creator_id, body.status, body.notes)
    return {"ok": True}


@app.get("/api/leads/export")
def export_leads():
    creators = get_top_creators(limit=10_000)

    def generate():
        if not creators:
            yield ""
            return
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=creators[0].keys())
        writer.writeheader()
        for row in creators:
            writer.writerow(row)
        yield buf.getvalue()

    filename = f"leads_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# Daily Queue endpoints
# ---------------------------------------------------------------------------

@app.get("/api/queue/today")
def queue_today():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    fill_queue_for_date(today, size=10)
    entries = get_queue_for_date(today)
    result = []
    for e in entries:
        posts = get_posts_for_creator(e["id"], limit=3)
        plan  = build_action_plan(e, posts)
        result.append({
            "queue_id":      e["queue_id"],
            "queue_status":  e["queue_status"],
            "contacted_at":  e["contacted_at"],
            "creator": {
                "id":              e["id"],
                "username":        e["username"],
                "full_name":       e["full_name"],
                "biography":       e["biography"],
                "followers":       e["followers"],
                "engagement_rate": e["engagement_rate"],
                "score":           e["score"],
                "niche_tags":      e["niche_tags"],
                "website":         e["website"],
            },
            "action": plan,
        })
    stats = get_queue_stats()
    return {"date": today, "items": result, "stats": stats}


@app.post("/api/queue/{queue_id}/done")
def mark_done(queue_id: int):
    mark_queue_item(queue_id, "done")
    # Also update creator status to "contacted"
    from database import get_db
    with get_db() as db:
        row = db.execute(
            "SELECT creator_id FROM daily_queue WHERE id = ?", (queue_id,)
        ).fetchone()
        if row:
            update_creator_status(row["creator_id"], "contacted")
    return {"ok": True}


@app.post("/api/queue/{queue_id}/skip")
def mark_skip(queue_id: int):
    mark_queue_item(queue_id, "skipped")
    return {"ok": True}


@app.get("/api/queue/stats")
def queue_stats():
    return get_queue_stats()


# ---------------------------------------------------------------------------
# Hashtags endpoint
# ---------------------------------------------------------------------------

@app.get("/api/hashtags")
def hashtags():
    from database import get_db
    with get_db() as db:
        rows = db.execute("SELECT id, name, last_synced FROM hashtags ORDER BY name").fetchall()
    synced = [dict(r) for r in rows]
    return {"configured": config.HASHTAGS, "synced": synced}


# ---------------------------------------------------------------------------
# Discovery endpoints
# ---------------------------------------------------------------------------

def _run_discovery(run_id: str, hashtags: list[str], mode: str, media_limit: int):
    with _run_lock:
        run_state["log_lines"] = []
        run_state["started_at"] = datetime.utcnow().isoformat()

    try:
        results = engine.run_full_discovery(
            hashtags=hashtags, mode=mode, media_limit=media_limit
        )
        with _run_lock:
            run_state["status"]        = "done"
            run_state["results_count"] = len(results)
            run_state["finished_at"]   = datetime.utcnow().isoformat()
    except Exception as e:
        with _run_lock:
            run_state["status"]      = "error"
            run_state["finished_at"] = datetime.utcnow().isoformat()
            run_state["log_lines"].append(f"ERROR: {e}")


@app.post("/api/discovery/run")
def start_discovery(body: DiscoveryRunRequest):
    with _run_lock:
        if run_state["status"] == "running":
            raise HTTPException(status_code=409, detail="A discovery run is already in progress.")
        run_id = str(uuid.uuid4())
        run_state["status"]  = "running"
        run_state["run_id"]  = run_id
        run_state["results_count"] = 0

    hashtags = body.hashtags or config.HASHTAGS
    t = threading.Thread(
        target=_run_discovery,
        args=(run_id, hashtags, body.mode, body.media_limit),
        daemon=True,
    )
    t.start()
    return {"run_id": run_id, "status": "running"}


@app.get("/api/discovery/status")
def discovery_status():
    with _run_lock:
        return {
            "status":        run_state["status"],
            "run_id":        run_state["run_id"],
            "started_at":    run_state["started_at"],
            "finished_at":   run_state["finished_at"],
            "results_count": run_state["results_count"],
            "recent_logs":   run_state["log_lines"][-50:],
        }


@app.get("/api/discovery/stream")
async def discovery_stream():
    async def event_generator():
        cursor = 0
        import asyncio
        while True:
            with _run_lock:
                lines = run_state["log_lines"]
                status = run_state["status"]

            while cursor < len(lines):
                yield {"data": lines[cursor]}
                cursor += 1

            if status in ("done", "error", "idle") and cursor >= len(lines):
                yield {"event": "done", "data": status}
                break

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
