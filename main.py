"""
FastAPI Application Entry Point
Production-Grade AI for Technical Support & TAM Teams
"""

import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from src.config import settings
from src.schemas import (
    TicketTriageRequest,
    TicketTriageResult,
    TAMAccountBrief,
    EvalSummaryReport,
    RunEvalRequest
)
from src.agents import triage_agent, tam_agent
from src.eval_harness import eval_harness
from src.data_loader import data_loader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

app = FastAPI(
    title="Support & TAM AI Platform",
    description="Production-Grade AI for Technical Support & TAM Teams powered by NVIDIA NIM & NOOA Architecture",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ==============================================================================
# UI Dashboard Routes
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard_view(request: Request):
    """
    Renders the unified 3-tab management dashboard.
    """
    accounts = data_loader.get_all_accounts()
    tickets = data_loader.get_all_tickets()[:20]  # Sample first 20 for selector
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "accounts": accounts,
            "tickets": tickets,
            "prompt_version": settings.prompt_version
        }
    )


# ==============================================================================
# API Endpoints (Task 1, 2, 3)
# ==============================================================================

@app.post("/api/v1/triage", response_model=TicketTriageResult)
async def triage_ticket_endpoint(payload: TicketTriageRequest):
    """
    Task 1: Ingest raw ticket text, classify area, category, urgency (P1-P4),
    match BM25 KB snippet, assign responder team, and draft response.
    """
    try:
        result = await triage_agent.triage(payload.subject, payload.body)
        return result
    except Exception as e:
        logger.error(f"Triage error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tam-brief/{account_id}", response_model=TAMAccountBrief)
async def tam_brief_endpoint(account_id: str):
    """
    Task 2: Ingest account ID, aggregate 90-day ticket history, produce a deterministic
    3-section brief with 100% verified verbatim quotes for churn/escalation signals.
    """
    try:
        brief = await tam_agent.generate_brief(account_id)
        return brief
    except Exception as e:
        logger.error(f"TAM brief error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/run-evals", response_model=EvalSummaryReport)
async def run_evals_endpoint(payload: Optional[RunEvalRequest] = None):
    """
    Task 3: Run automated evaluation benchmark harness across standard, edge,
    and adversarial test cases and export eval_report.json.
    """
    try:
        run_adv = payload.run_adversarial if payload else True
        report = await eval_harness.run_all(run_adversarial=run_adv)
        return report
    except Exception as e:
        logger.error(f"Evaluation harness error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stream-evals")
async def stream_evals_endpoint(run_adversarial: bool = True):
    """
    Bonus: Real-time Server-Sent Events (SSE) stream yielding test progress live per case.
    """
    return StreamingResponse(
        eval_harness.stream_all(run_adversarial=run_adversarial),
        media_type="text/event-stream"
    )


# Helper sample endpoints for frontend loaders
@app.get("/api/v1/accounts")
async def get_accounts_list():
    return data_loader.get_all_accounts()


@app.get("/api/v1/tickets")
async def get_tickets_list():
    return data_loader.get_all_tickets()[:30]


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "tickets_loaded": len(data_loader.get_all_tickets()),
        "accounts_loaded": len(data_loader.get_all_accounts())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)
