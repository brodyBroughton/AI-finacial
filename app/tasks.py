"""Celery tasks for running long-running analysis workflows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from app import db
from app.celery_app import celery
from app.services.analyze import analyze


logger = logging.getLogger(__name__)


def _flag(job: dict[str, Any], keys: Iterable[str], default: bool = True) -> bool:
    """Return the first truthy/falsey value found for any of the keys."""

    for key in keys:
        if key in job and job[key] is not None:
            return bool(job[key])
    return default


def _has_required_outputs(
    storage: dict[str, Any] | None,
    need_facts: bool,
    need_insights: bool,
) -> bool:
    """Whether storage already satisfies the requested outputs."""

    if not storage:
        return False
    if storage.get("new_data"):
        return False

    has_facts = (not need_facts) or (storage.get("facts_output") is not None)
    has_insights = (not need_insights) or (storage.get("insights_output") is not None)
    return has_facts and has_insights


@celery.task(name="run_analysis_job")
def run_analysis_job(job_id: str) -> dict[str, Any]:
    """
    Fetch job metadata, run analysis if needed, and persist outputs.

    This task acquires a Postgres advisory lock per ticker to avoid duplicate
    OpenAI work when multiple jobs race for the same ticker.
    """

    job = db.get_job(job_id)
    if not job:
        raise RuntimeError(f"analysis_jobs row {job_id} not found")

    id_column = db.infer_job_id_column(job)
    ticker = job.get("ticker") or job.get("symbol")
    if not ticker:
        raise RuntimeError("Job is missing ticker/symbol column")

    enable_facts = _flag(job, ("enable_facts", "facts_enabled", "include_facts"), default=True)
    enable_insights = _flag(
        job, ("enable_insights", "insights_enabled", "include_insights"), default=True
    )

    started_at = datetime.now(timezone.utc)
    db.set_job_status(
        job_id,
        status="RUNNING",
        started_at=started_at,
        finished_at=None,
        error=None,
        id_column=id_column,
    )

    storage_id = None
    try:
        with db.ticker_locked_conn(ticker) as conn:
            storage = db.get_storage_by_ticker(ticker, conn=conn, for_update=True)
            if _has_required_outputs(storage, enable_facts, enable_insights):
                storage_id = storage.get("id") or storage.get("storage_id")
                result_storage = storage
            else:
                outputs = analyze(
                    ticker,
                    enable_facts=enable_facts,
                    enable_insights=enable_insights,
                )
                result_storage = db.upsert_storage_for_ticker(
                    ticker,
                    analysis_input_doc=outputs.get("analysis_input_doc"),
                    facts_output=outputs.get("facts_output"),
                    insights_output=outputs.get("insights_output"),
                    new_data=False,
                    conn=conn,
                )
                storage_id = result_storage.get("id") or result_storage.get("storage_id")

        db.set_job_status(
            job_id,
            status="SUCCEEDED",
            started_at=None,
            finished_at=datetime.now(timezone.utc),
            error=None,
            storage_id=storage_id,
            id_column=id_column,
        )
        return result_storage
    except Exception as exc:  # pragma: no cover - Celery worker path
        logger.exception("run_analysis_job failed for %s: %s", job_id, exc)
        db.set_job_status(
            job_id,
            status="FAILED",
            started_at=None,
            finished_at=datetime.now(timezone.utc),
            error=str(exc),
            id_column=id_column,
        )
        raise
