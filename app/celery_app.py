"""Celery application setup for background analysis jobs."""

from __future__ import annotations

import os

from celery import Celery
from dotenv import load_dotenv


load_dotenv()

broker_url = os.environ.get("CELERY_BROKER_URL")
if not broker_url:
    raise RuntimeError("CELERY_BROKER_URL is required for Celery to start.")

celery = Celery(
    "ai_financial",
    broker=broker_url,
    include=["app.tasks"],
)

celery.conf.update(
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_track_started=True,
    task_soft_time_limit=480,
    task_time_limit=600,
    timezone="UTC",
)
