"""Shared analysis pipeline used by both the API and Celery worker."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi.encoders import jsonable_encoder

from facts_lookup import run_facts_lookup
from orgvsinorg import fetch_item2, run_orgvsinorg


load_dotenv()


def _build_analysis_input_doc(ticker: str, use_cache: bool = True) -> Dict[str, Any]:
    """Collect the minimal 10-Q context we want to persist alongside outputs."""

    fetched = fetch_item2(ticker, use_cache=use_cache)
    if not fetched:
        return {
            "ticker": ticker.lower(),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "item2_content": None,
            "stockinfo": None,
        }

    item2_content, stockinfo = fetched
    return {
        "ticker": ticker.lower(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "item2_content": item2_content,
        "stockinfo": stockinfo,
    }


def analyze(
    ticker: str,
    enable_facts: bool = True,
    enable_insights: bool = True,
    use_cache: bool = True,
) -> Dict[str, Optional[Any]]:
    """
    Run the long-form analysis flow.

    This is the single entry point used by FastAPI endpoints and Celery tasks
    so that OpenAI/EDGAR work happens in one place.
    """

    analysis_input_doc = _build_analysis_input_doc(ticker, use_cache=use_cache)

    facts_output = run_facts_lookup(ticker) if enable_facts else None
    insights_output = (
        run_orgvsinorg(ticker, use_cache=use_cache) if enable_insights else None
    )

    return jsonable_encoder(
        {
            "analysis_input_doc": analysis_input_doc,
            "facts_output": facts_output,
            "insights_output": insights_output,
        }
    )
