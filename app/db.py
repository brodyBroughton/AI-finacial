"""Lightweight database helper layer shared by API and Celery worker."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import psycopg
from psycopg import sql
from psycopg.errors import UndefinedColumn
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import ConnectionPool


DATABASE_URL = os.environ.get("DATABASE_URL")

pool = ConnectionPool(
    DATABASE_URL,
    open=False,
    kwargs={
        "autocommit": False,
        "row_factory": dict_row,
    },
)


def _ensure_pool_open() -> ConnectionPool:
    if not pool.is_open():
        pool.open()
    return pool


@contextmanager
def connection():
    """Yield a pooled connection with dict rows."""

    _ensure_pool_open()
    with pool.connection() as conn:
        yield conn


@contextmanager
def ticker_locked_conn(ticker: str):
    """
    Acquire a transaction-scoped advisory lock for a ticker.

    This prevents two workers from running expensive OpenAI work for the same
    ticker concurrently. The lock is released when the transaction ends.
    """

    _ensure_pool_open()
    with pool.connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (ticker.lower(),))
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _get_job_with_column(job_id: str, column: str) -> Optional[Dict[str, Any]]:
    with connection() as conn, conn.cursor() as cur:
        try:
            cur.execute(
                sql.SQL("SELECT * FROM analysis_jobs WHERE {} = %s").format(sql.Identifier(column)),
                (job_id,),
            )
            return cur.fetchone()
        except UndefinedColumn:
            return None


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a job by id (tries both `id` and `job_id` columns)."""

    for column in ("id", "job_id"):
        job = _get_job_with_column(job_id, column)
        if job:
            return job
    return None


def infer_job_id_column(job: Dict[str, Any]) -> str:
    """Return which column name to use when updating a job record."""

    return "id" if "id" in job else "job_id"


def set_job_status(
    job_id: str,
    status: str,
    *,
    started_at: datetime | None,
    finished_at: datetime | None,
    error: str | None,
    storage_id: Any | None = None,
    id_column: str = "id",
) -> Optional[Dict[str, Any]]:
    """Update job status and timestamps atomically."""

    set_clauses = ["status = %(status)s"]
    params: Dict[str, Any] = {"status": status, "job_id": job_id}
    if started_at is not None:
        set_clauses.append("started_at = %(started_at)s")
        params["started_at"] = started_at
    if finished_at is not None:
        set_clauses.append("finished_at = %(finished_at)s")
        params["finished_at"] = finished_at
    set_clauses.append("error = %(error)s")
    params["error"] = error
    if storage_id is not None:
        set_clauses.append("storage_id = %(storage_id)s")
        params["storage_id"] = storage_id

    query = sql.SQL("UPDATE analysis_jobs SET {} WHERE {} = %(job_id)s RETURNING *").format(
        sql.SQL(", ").join(sql.SQL(part) for part in set_clauses),
        sql.Identifier(id_column),
    )

    with connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()


def get_storage_by_ticker(
    ticker: str,
    *,
    conn=None,
    for_update: bool = False,
) -> Optional[Dict[str, Any]]:
    """Return the storage row for this ticker."""

    sql_text = "SELECT * FROM analysis_storage WHERE ticker = %s"
    if for_update:
        sql_text += " FOR UPDATE"

    if conn is None:
        with connection() as conn_ctx, conn_ctx.cursor() as cur:
            cur.execute(sql_text, (ticker.lower(),))
            return cur.fetchone()

    with conn.cursor() as cur:
        cur.execute(sql_text, (ticker.lower(),))
        return cur.fetchone()


def upsert_storage_for_ticker(
    ticker: str,
    analysis_input_doc: Dict[str, Any],
    facts_output: Any,
    insights_output: Any,
    *,
    new_data: bool = False,
    conn=None,
) -> Dict[str, Any]:
    """
    Insert or update the storage row for this ticker.

    This uses a single upsert inside an advisory-locked transaction (caller
    should pass the same `conn` obtained from `ticker_locked_conn`).
    """

    params = (
        ticker.lower(),
        Json(analysis_input_doc),
        Json(facts_output) if facts_output is not None else None,
        Json(insights_output) if insights_output is not None else None,
        new_data,
    )

    query = """
        INSERT INTO analysis_storage (ticker, analysis_input_doc, facts_output, insights_output, new_data)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (ticker)
        DO UPDATE SET
            analysis_input_doc = EXCLUDED.analysis_input_doc,
            facts_output = COALESCE(EXCLUDED.facts_output, analysis_storage.facts_output),
            insights_output = COALESCE(EXCLUDED.insights_output, analysis_storage.insights_output),
            new_data = EXCLUDED.new_data
        RETURNING *
    """

    if conn is None:
        with ticker_locked_conn(ticker) as conn_ctx, conn_ctx.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()

    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()


def set_storage_new_data(ticker: str, new_data: bool) -> Optional[Dict[str, Any]]:
    """Flip the new_data flag for a ticker (without touching outputs)."""

    query = """
        UPDATE analysis_storage
           SET new_data = %s
         WHERE ticker = %s
     RETURNING *
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(query, (new_data, ticker.lower()))
        return cur.fetchone()
