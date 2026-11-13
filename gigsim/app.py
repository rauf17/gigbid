"""FastAPI Application for GigSim (AI-4016 GigBid Phase 1b Part 3).

REST API simulator providing:
  - Job streams with release ticking (/jobs, /jobs/{id})
  - Public client profiles (/clients/{id}) with zero leakage of hidden preferences
  - Connects balance management and spending (/connects/balance)
  - Dry-run and idempotent proposal submission (/proposals, /proposals/{id}/submit)
  - Client messaging channels (/conversations, /conversations/{id}/messages)
  - Administrative control (/admin/tick, /admin/reset)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, Query

from gigsim.clients import evaluate_proposal
from gigsim.models import (
    ConnectsBalanceResponse,
    ConversationResponse,
    HealthResponse,
    JobListResponse,
    JobPublic,
    MessageCreateRequest,
    MessageResponse,
    ProposalCreateRequest,
    ProposalResponse,
    ProposalSubmitResponse,
    ResetResponse,
    TickResponse,
)
from gigsim.ratelimit import GigSimMiddleware
from gigsim.seed import get_db_connection, reset_database, seed_database

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = Path(__file__).resolve().parent / "seed"
RULES_FILE = SEED_DIR / "platform_rules.yaml"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database is seeded on startup
    conn = get_db_connection()
    seed_database(conn)
    yield


app = FastAPI(
    title="GigSim",
    description="Student-built freelance marketplace simulator (AI-4016 GigBid)",
    version="0.1.0",
    lifespan=lifespan,
)

# Attach rate limiting, token authentication, and fault injection middleware
app.add_middleware(GigSimMiddleware, rules_path=str(RULES_FILE))


def get_db() -> sqlite3.Connection:
    return get_db_connection()


def get_simulated_time(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM meta WHERE key = 'simulated_time'").fetchone()
    return row["value"] if row else "2024-08-01T12:00:00Z"


def get_balance(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM meta WHERE key = 'connects_balance'").fetchone()
    return int(row["value"]) if row else 150


def load_platform_rules() -> dict[str, Any]:
    if RULES_FILE.exists():
        return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8")) or {}
    return {}


@app.get("/health", response_model=HealthResponse)
def health_check(conn: Annotated[sqlite3.Connection, Depends(get_db)]):
    sim_time = get_simulated_time(conn)
    balance = get_balance(conn)
    released_count = conn.execute("SELECT COUNT(*) AS c FROM jobs WHERE is_released = 1").fetchone()["c"]
    active_props = conn.execute(
        "SELECT COUNT(*) AS c FROM proposals WHERE status IN ('submitted', 'viewed', 'replied', 'interview')"
    ).fetchone()["c"]
    return HealthResponse(
        status="healthy",
        simulated_time=sim_time,
        released_jobs_count=released_count,
        connects_balance=balance,
        active_proposals_count=active_props,
    )


@app.get("/jobs", response_model=JobListResponse)
def list_jobs(
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
    q: str | None = None,
    category: str | None = None,
    since: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
):
    query = "SELECT * FROM jobs WHERE is_released = 1"
    params: list[Any] = []

    if q:
        query += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])

    if category:
        query += " AND category = ?"
        params.append(category)

    if since:
        query += " AND posted_at >= ?"
        params.append(since)

    if cursor:
        try:
            cursor_order = int(cursor)
            query += " AND released_order > ?"
            params.append(cursor_order)
        except ValueError:
            pass

    query += " ORDER BY released_order ASC LIMIT ?"
    params.append(limit + 1)

    rows = conn.execute(query, params).fetchall()
    items: list[JobPublic] = []
    has_more = len(rows) > limit
    returned_rows = rows[:limit]

    for r in returned_rows:
        items.append(
            JobPublic(
                id=r["id"],
                title=r["title"],
                description=r["description"],
                category=r["category"],
                skills=json.loads(r["skills_json"]),
                budget_type=r["budget_type"],
                budget_min=r["budget_min"],
                budget_max=r["budget_max"],
                client_country=r["client_country"],
                client_id=r["client_id"],
                posted_at=r["posted_at"],
                connects_cost=r["connects_cost"],
                synthetic=bool(r["synthetic"]),
            )
        )

    next_cursor = str(returned_rows[-1]["released_order"]) if has_more and returned_rows else None
    total_count = conn.execute("SELECT COUNT(*) AS c FROM jobs WHERE is_released = 1").fetchone()["c"]

    return JobListResponse(
        items=items,
        next_cursor=next_cursor,
        total=total_count,
    )


@app.get("/jobs/{job_id}", response_model=JobPublic)
def get_job(job_id: str, conn: Annotated[sqlite3.Connection, Depends(get_db)]):
    row = conn.execute("SELECT * FROM jobs WHERE id = ? AND is_released = 1", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found or not yet released.")
    return JobPublic(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        category=row["category"],
        skills=json.loads(row["skills_json"]),
        budget_type=row["budget_type"],
        budget_min=row["budget_min"],
        budget_max=row["budget_max"],
        client_country=row["client_country"],
        client_id=row["client_id"],
        posted_at=row["posted_at"],
        connects_cost=row["connects_cost"],
        synthetic=bool(row["synthetic"]),
    )


@app.get("/clients/{client_id}")
def get_client(client_id: str, conn: Annotated[sqlite3.Connection, Depends(get_db)]):
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Client not found.")
    # Return strictly public fields. Hidden evaluation preferences are never leaked.
    return {
        "id": row["id"],
        "company": row["company"],
        "industry": row["industry"],
        "country": row["country"],
        "payment_verified": bool(row["payment_verified"]),
        "total_spent": row["total_spent"],
        "hire_rate": row["hire_rate"],
        "avg_rating": row["avg_rating"],
        "jobs_posted": row["jobs_posted"],
        "review_count": row["review_count"],
    }


@app.get("/connects/balance", response_model=ConnectsBalanceResponse)
def get_connects_balance(conn: Annotated[sqlite3.Connection, Depends(get_db)]):
    balance = get_balance(conn)
    row_grant = conn.execute("SELECT value FROM meta WHERE key = 'weekly_grant'").fetchone()
    weekly_grant = int(row_grant["value"]) if row_grant else 80
    row_date = conn.execute("SELECT value FROM meta WHERE key = 'last_grant_date'").fetchone()
    last_date = row_date["value"] if row_date else get_simulated_time(conn)

    return ConnectsBalanceResponse(
        balance=balance,
        currency="connects",
        weekly_grant=weekly_grant,
        last_grant_date=last_date,
    )


@app.post("/proposals", response_model=ProposalResponse)
def create_proposal(
    body: ProposalCreateRequest,
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    # 1. Idempotency Check
    if idempotency_key:
        cached = conn.execute("SELECT * FROM idempotency_cache WHERE key = ?", (idempotency_key,)).fetchone()
        if cached:
            return json.loads(cached["response_json"])

    # 2. Validate Job
    job = conn.execute("SELECT * FROM jobs WHERE id = ? AND is_released = 1", (body.job_id,)).fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or not yet released.")

    connects_cost = job["connects_cost"]
    sim_time = get_simulated_time(conn)

    # 3. Dry-Run Check (returns what would be stored/sent + connects cost; no Connects spent, no DB insert)
    if body.dry_run:
        resp = ProposalResponse(
            id=body.id or f"draft_preview_{body.job_id}",
            job_id=body.job_id,
            cover_letter=body.cover_letter,
            screening_answers=body.screening_answers,
            bid_amount=body.bid_amount,
            connects_cost=connects_cost,
            status="draft",
            created_at=sim_time,
            dry_run=True,
            message="Dry run successful. Proposal draft preview generated; no Connects spent.",
        )
        return resp

    # 4. Create Draft Proposal (no Connects spent until /submit)
    prop_id = body.id or f"prop_{uuid4().hex[:10]}"
    answers_json = json.dumps(body.screening_answers) if body.screening_answers else None

    with conn:
        conn.execute("""
        INSERT INTO proposals (
            id, job_id, cover_letter, screening_answers_json, bid_amount,
            connects_cost, status, created_at, idempotency_key
        ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?)
        """, (
            prop_id, body.job_id, body.cover_letter, answers_json,
            body.bid_amount, connects_cost, sim_time, idempotency_key
        ))

    resp_obj = ProposalResponse(
        id=prop_id,
        job_id=body.job_id,
        cover_letter=body.cover_letter,
        screening_answers=body.screening_answers,
        bid_amount=body.bid_amount,
        connects_cost=connects_cost,
        status="draft",
        created_at=sim_time,
        dry_run=False,
        message="Proposal created in draft status. Submit via /proposals/{id}/submit to spend Connects.",
    )

    if idempotency_key:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO idempotency_cache (key, endpoint, response_json, status_code, created_at) VALUES (?, ?, ?, ?, ?)",
                (idempotency_key, "/proposals", json.dumps(resp_obj.model_dump()), 200, sim_time)
            )

    return resp_obj


@app.post("/proposals/{proposal_id}/submit", response_model=ProposalSubmitResponse)
def submit_proposal(
    proposal_id: str,
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    # Check Idempotency Cache
    if idempotency_key:
        cached = conn.execute("SELECT * FROM idempotency_cache WHERE key = ?", (idempotency_key,)).fetchone()
        if cached:
            return json.loads(cached["response_json"])

    prop = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    balance = get_balance(conn)
    sim_time = get_simulated_time(conn)

    # If already submitted, return existing record without double-charging Connects
    if prop["status"] != "draft":
        return ProposalSubmitResponse(
            id=prop["id"],
            job_id=prop["job_id"],
            status=prop["status"],
            connects_cost=prop["connects_cost"],
            connects_balance=balance,
            submitted_at=prop["submitted_at"] or sim_time,
            message="Proposal was already submitted. No additional Connects charged.",
        )

    # Check connects balance
    connects_cost = prop["connects_cost"]
    if balance < connects_cost:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient Connects balance. Required: {connects_cost}, Available: {balance}."
        )

    # Deduct Connects and update status
    new_balance = balance - connects_cost
    with conn:
        conn.execute("UPDATE meta SET value = ? WHERE key = 'connects_balance'", (str(new_balance),))
        conn.execute(
            "UPDATE proposals SET status = 'submitted', submitted_at = ?, idempotency_key = ? WHERE id = ?",
            (sim_time, idempotency_key, proposal_id)
        )

    resp_obj = ProposalSubmitResponse(
        id=proposal_id,
        job_id=prop["job_id"],
        status="submitted",
        connects_cost=connects_cost,
        connects_balance=new_balance,
        submitted_at=sim_time,
        message=f"Proposal submitted successfully. Charged {connects_cost} Connects.",
    )

    if idempotency_key:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO idempotency_cache (key, endpoint, response_json, status_code, created_at) VALUES (?, ?, ?, ?, ?)",
                (idempotency_key, f"/proposals/{proposal_id}/submit", json.dumps(resp_obj.model_dump()), 200, sim_time)
            )

    return resp_obj


@app.get("/proposals")
def list_proposals(
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
    status: str | None = None,
):
    if status:
        rows = conn.execute("SELECT * FROM proposals WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM proposals ORDER BY created_at DESC").fetchall()

    return [
        {
            "id": r["id"],
            "job_id": r["job_id"],
            "cover_letter": r["cover_letter"],
            "bid_amount": r["bid_amount"],
            "connects_cost": r["connects_cost"],
            "status": r["status"],
            "created_at": r["created_at"],
            "submitted_at": r["submitted_at"],
            "client_feedback": r["client_feedback"],
        }
        for r in rows
    ]


@app.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(conn: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
    items = []
    for r in rows:
        latest = conn.execute(
            "SELECT text FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1",
            (r["id"],)
        ).fetchone()
        items.append(
            ConversationResponse(
                id=r["id"],
                proposal_id=r["proposal_id"],
                job_id=r["job_id"],
                client_id=r["client_id"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                latest_message=latest["text"] if latest else None,
            )
        )
    return items


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def get_messages(conversation_id: str, conn: Annotated[sqlite3.Connection, Depends(get_db)]):
    conv = conn.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    rows = conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
        (conversation_id,)
    ).fetchall()
    return [
        MessageResponse(
            id=r["id"],
            conversation_id=r["conversation_id"],
            sender=r["sender"],
            text=r["text"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


@app.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
def send_message(
    conversation_id: str,
    body: MessageCreateRequest,
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    if idempotency_key:
        cached = conn.execute("SELECT * FROM idempotency_cache WHERE key = ?", (idempotency_key,)).fetchone()
        if cached:
            return json.loads(cached["response_json"])

    conv = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    sim_time = get_simulated_time(conn)
    msg_id = f"msg_{uuid4().hex[:10]}"

    with conn:
        conn.execute("""
        INSERT INTO messages (id, conversation_id, sender, text, created_at, idempotency_key)
        VALUES (?, ?, 'freelancer', ?, ?, ?)
        """, (msg_id, conversation_id, body.text, sim_time, idempotency_key))

        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (sim_time, conversation_id))

    resp_obj = MessageResponse(
        id=msg_id,
        conversation_id=conversation_id,
        sender="freelancer",
        text=body.text,
        created_at=sim_time,
    )

    if idempotency_key:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO idempotency_cache (key, endpoint, response_json, status_code, created_at) VALUES (?, ?, ?, ?, ?)",
                (idempotency_key, f"/conversations/{conversation_id}/messages", json.dumps(resp_obj.model_dump()), 200, sim_time)
            )

    return resp_obj


@app.post("/admin/tick", response_model=TickResponse)
def admin_tick(
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
    n: int = Query(default=5, ge=1, le=100),
):
    """Advances simulation: releases n jobs and evaluates submitted proposals."""
    # 1. Release next n jobs
    unreleased = conn.execute(
        "SELECT id FROM jobs WHERE is_released = 0 ORDER BY released_order ASC LIMIT ?", (n,)
    ).fetchall()

    released_count = len(unreleased)
    if unreleased:
        ids = [r["id"] for r in unreleased]
        placeholders = ",".join(["?"] * len(ids))
        with conn:
            conn.execute(f"UPDATE jobs SET is_released = 1 WHERE id IN ({placeholders})", ids)

    total_released = conn.execute("SELECT COUNT(*) AS c FROM jobs WHERE is_released = 1").fetchone()["c"]

    # 2. Advance simulated time by 24 hours
    current_time_str = get_simulated_time(conn)
    current_dt = datetime.fromisoformat(current_time_str)
    advanced_dt = current_dt + timedelta(hours=24)
    new_sim_time = advanced_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    with conn:
        conn.execute("UPDATE meta SET value = ? WHERE key = 'simulated_time'", (new_sim_time,))

    # 3. Fast deterministic evaluation of submitted proposals using Client Decision Engine
    submitted_props = conn.execute("""
    SELECT p.*, j.client_id, j.title AS job_title, j.description AS job_desc,
           j.posted_at AS job_posted_at, j.skills_json AS job_skills_json, j.category AS job_category,
           c.company, c.industry, c.country, c.payment_verified, c.total_spent,
           c.hire_rate, c.avg_rating, c.jobs_posted, c.review_count, c.hidden_json
    FROM proposals p
    JOIN jobs j ON p.job_id = j.id
    JOIN clients c ON j.client_id = c.id
    WHERE p.status = 'submitted'
    """).fetchall()

    rules = load_platform_rules()
    client_llm = rules.get("simulation", {}).get("client_llm", False)
    updates: list[dict[str, Any]] = []

    for prop in submitted_props:
        hidden = json.loads(prop["hidden_json"])
        client_public = {
            "company": prop["company"],
            "industry": prop["industry"],
            "country": prop["country"],
            "payment_verified": bool(prop["payment_verified"]),
            "total_spent": prop["total_spent"],
            "hire_rate": prop["hire_rate"],
            "avg_rating": prop["avg_rating"],
            "jobs_posted": prop["jobs_posted"],
            "review_count": prop["review_count"],
        }
        job_data = {
            "title": prop["job_title"],
            "description": prop["job_desc"],
            "posted_at": prop["job_posted_at"],
            "skills": json.loads(prop["job_skills_json"]) if prop["job_skills_json"] else [],
            "category": prop["job_category"],
            "company": prop["company"],
        }

        # Check for scam indicators
        desc_lower = str(prop["job_desc"]).lower()
        is_scam = (
            (not bool(prop["payment_verified"]) and prop["total_spent"] == 0)
            or any(s in desc_lower for s in ["telegram", "whatsapp", "crypto", "unpaid test"])
        )

        eval_res = evaluate_proposal(
            proposal=dict(prop),
            client_hidden=hidden,
            job=job_data,
            client_public=client_public,
            is_scam=is_scam,
            client_llm=client_llm,
        )

        with conn:
            conn.execute(
                "UPDATE proposals SET status = ?, score = ?, client_feedback = ? WHERE id = ?",
                (eval_res.status, eval_res.score, eval_res.feedback, prop["id"])
            )

            # If client replied, invited to interview, or hired, create conversation and client message
            if eval_res.status in {"replied", "interview", "hired"} and eval_res.message:
                conv_id = f"conv_{uuid4().hex[:8]}"
                msg_id = f"msg_{uuid4().hex[:8]}"
                conn.execute(
                    "INSERT INTO conversations (id, proposal_id, job_id, client_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (conv_id, prop["id"], prop["job_id"], prop["client_id"], new_sim_time, new_sim_time)
                )

                conn.execute(
                    "INSERT INTO messages (id, conversation_id, sender, text, created_at) VALUES (?, ?, 'client', ?, ?)",
                    (msg_id, conv_id, eval_res.message, new_sim_time)
                )

        updates.append({"id": prop["id"], "status": eval_res.status, "score": eval_res.score, "client_id": prop["client_id"]})

    return TickResponse(
        released_jobs=released_count,
        total_released=total_released,
        advanced_time=new_sim_time,
        proposals_evaluated=len(submitted_props),
        status_updates=updates,
    )


@app.post("/admin/reset", response_model=ResetResponse)
def admin_reset(conn: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Resets simulator database state to initial seed."""
    reset_database(conn)
    return ResetResponse(
        status="reset",
        message="Simulator database reset to initial seed state."
    )
