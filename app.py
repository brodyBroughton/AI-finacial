"""FastAPI service for financial analysis workflows."""

import os
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from facts_lookup import run_facts_lookup
from orgvsinorg import run_orgvsinorg


app = FastAPI(title="AI Financial Service")


def require_env() -> None:
    """Ensure required environment variables are set."""

    required = ("OPENAI_API_KEY", "GOOGLE_API_KEY", "PYTHON_API_TOKEN")
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


@app.post("/analysis/facts")
def analysis_facts(payload: FactsRequest, _: None = Depends(require_auth)) -> dict:
    """Return EPS, cashflow, and revenue summaries for a ticker."""

    result = run_facts_lookup(payload.ticker)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticker not found.")
    return jsonable_encoder(result)


@app.post("/analysis/insights")
def analysis_insights(payload: InsightsRequest, _: None = Depends(require_auth)) -> dict:
    """Return revenue, cashflow, and debt insights for a ticker."""

    result = run_orgvsinorg(payload.ticker, use_cache=payload.use_cache)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticker not found.")
    return jsonable_encoder(result)
