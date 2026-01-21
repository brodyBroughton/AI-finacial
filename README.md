# AI Financial FastAPI Service

FastAPI wrapper around the existing SEC facts lookup and 10‑Q analysis scripts,
now with Celery + Redis background processing and shared Postgres persistence.

## Requirements

- Python 3.11+
- Required environment variables:
  - `OPENAI_API_KEY`
  - `GOOGLE_API_KEY`
  - `PYTHON_API_TOKEN`
  - `DATABASE_URL` (same Postgres used by the Next.js/Prisma app)
  - `CELERY_BROKER_URL` (Redis connection string)
- Optional:
  - `SEC_USER_AGENT` (overrides default SEC user agent)
  - `API_BASE_URL` (used by the smoke test script)

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AIza..."
export PYTHON_API_TOKEN="local-dev-token"
export DATABASE_URL="postgres://user:pass@localhost:5432/ai_financial"
export CELERY_BROKER_URL="redis://localhost:6379/0"
export SEC_USER_AGENT="your name you@example.com"
export API_BASE_URL="http://localhost:8000"

uvicorn app.main:app --host 0.0.0.0 --port 8000
# in another terminal
celery -A app.celery_app.celery worker --loglevel=INFO --concurrency=1
```

## Docker

```bash
docker build -t ai-financial-service .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY="sk-..." \
  -e GOOGLE_API_KEY="AIza..." \
  -e PYTHON_API_TOKEN="local-dev-token" \
  -e DATABASE_URL="postgres://user:pass@postgres:5432/ai_financial" \
  -e CELERY_BROKER_URL="redis://redis:6379/0" \
  -e SEC_USER_AGENT="your name you@example.com" \
  ai-financial-service
```

## Local dev with Docker Compose

```bash
cp .env.example .env  # create .env with your secrets (OPENAI_API_KEY, etc.)
docker-compose up --build api worker
```

Services started:
- Postgres (service `postgres`)
- Redis (service `redis`)
- FastAPI web (`api`, port 8000)
- Celery worker (`worker`) consuming from Redis and writing to Postgres

## Authentication

Every request must include:

```
Authorization: Bearer <PYTHON_API_TOKEN>
```

## API

### POST /analysis/facts
```json
{ "ticker": "aapl" }
```

### POST /analysis/insights
```json
{ "ticker": "aapl", "useCache": true }
```

### POST /jobs/enqueue
```json
{ "jobId": "<existing analysis_jobs id>" }
```
Returns 202 after placing a Celery message on Redis.

### GET /jobs/{jobId}
Token-protected debug endpoint that returns the raw `analysis_jobs` row.

## Background processing (Celery)

- Broker: Redis (`CELERY_BROKER_URL`); no Postgres polling.
- Worker command: `celery -A app.celery_app.celery worker --loglevel=INFO --concurrency=1`
- Task: `run_analysis_job` reads the job row, checks `analysis_storage.new_data`;
  reuses cached outputs when possible; otherwise runs facts/insights directly
  (no HTTP round trips) and upserts results inside an advisory-locked
  transaction.

## Smoke test script

```bash
export PYTHON_API_TOKEN="local-dev-token"
export API_BASE_URL="http://localhost:8000"
./scripts/smoke_test.sh
```

## Render deployment notes

- Web service command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Add a Background Worker service:
  `celery -A app.celery_app.celery worker --loglevel=INFO --concurrency=1`
- Add a Render Key Value instance (Redis) and set `CELERY_BROKER_URL` to its
  internal URL.
- Share the same Postgres `DATABASE_URL` between web and worker so results land
  in Prisma tables (`analysis_jobs`, `analysis_storage`).
- Shared env vars: `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `PYTHON_API_TOKEN`,
  `DATABASE_URL`, `CELERY_BROKER_URL`, optional `SEC_USER_AGENT`.
