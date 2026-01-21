"""FastAPI service for financial analysis workflows."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from app.db import get_job, infer_job_id_column, set_job_status
from app.services.analyze import analyze
from app.tasks import run_analysis_job


load_dotenv()

app = FastAPI(title="AI Financial Service")


def require_env() -> None:
    """Ensure required environment variables are set."""

    required = (
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "PYTHON_API_TOKEN",
        "DATABASE_URL",
        "CELERY_BROKER_URL",
    )
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )


@app.on_event("startup")
def startup_check() -> None:
    require_env()


def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Validate Bearer token authorization."""

    expected = os.environ.get("PYTHON_API_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PYTHON_API_TOKEN is not configured.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


class FactsRequest(BaseModel):
    """Request payload for facts lookup."""

    ticker: str = Field(..., min_length=1)


class InsightsRequest(BaseModel):
    """Request payload for insights analysis."""

    model_config = ConfigDict(populate_by_name=True)

    ticker: str = Field(..., min_length=1)
    use_cache: bool = Field(default=True, alias="useCache")


class JobEnqueueRequest(BaseModel):
    """Request payload for enqueuing a background analysis job."""

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(..., alias="jobId", min_length=1)


@app.post("/analysis/facts")
def analysis_facts(payload: FactsRequest, _: None = Depends(require_auth)) -> dict:
    """Return EPS, cashflow, and revenue summaries for a ticker."""

    result = analyze(ticker=payload.ticker, enable_facts=True, enable_insights=False)
    facts_output = result.get("facts_output") if isinstance(result, dict) else None
    if not facts_output:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticker not found.")
    return jsonable_encoder(facts_output)


@app.post("/analysis/insights")
def analysis_insights(payload: InsightsRequest, _: None = Depends(require_auth)) -> dict:
    """Return revenue, cashflow, and debt insights for a ticker."""

    result = analyze(
        ticker=payload.ticker,
        enable_facts=False,
        enable_insights=True,
        use_cache=payload.use_cache,
    )
    insights_output = result.get("insights_output") if isinstance(result, dict) else None
    if not insights_output:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticker not found.")
    return jsonable_encoder(insights_output)


@app.post("/jobs/enqueue", status_code=status.HTTP_202_ACCEPTED)
def enqueue_job(payload: JobEnqueueRequest, _: None = Depends(require_auth)) -> dict:
    """Enqueue a Celery task to run a stored analysis job."""

    job = get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    id_column = infer_job_id_column(job)
    set_job_status(
        payload.job_id,
        status="QUEUED",
        started_at=None,
        finished_at=None,
        error=None,
        id_column=id_column,
    )

    try:
        run_analysis_job.delay(payload.job_id)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to enqueue job: {exc}",
        ) from exc

    return {"jobId": payload.job_id, "status": "QUEUED"}


@app.get("/jobs/{job_id}")
def get_job_status(job_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
    """Return the current job record (for debugging/ops)."""

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return jsonable_encoder(job)
