# AI Financial FastAPI Service

FastAPI wrapper around the existing SEC facts lookup and 10‑Q analysis scripts.
The service exposes two POST endpoints that return JSON-only responses and
requires a Bearer token on every request.

## Requirements

- Python 3.11+
- Required environment variables:
  - `OPENAI_API_KEY`
  - `GOOGLE_API_KEY`
  - `PYTHON_API_TOKEN` (any strong random string you generate)
- Optional environment variable:
  - `SEC_USER_AGENT` (defaults to the existing in-code SEC user agent string)

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AIza..."
export PYTHON_API_TOKEN="local-dev-token"
export SEC_USER_AGENT="your name you@example.com"

uvicorn app:app --host 0.0.0.0 --port 8000
```

## Docker

```bash
docker build -t ai-financial-service .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY="sk-..." \
  -e GOOGLE_API_KEY="AIza..." \
  -e PYTHON_API_TOKEN="local-dev-token" \
  -e SEC_USER_AGENT="your name you@example.com" \
  ai-financial-service
```

## Authentication

Every request must include:

```
Authorization: Bearer <PYTHON_API_TOKEN>
```

Missing or invalid tokens return HTTP 401.
Generate a token however you like (for example, `python -c "import secrets; print(secrets.token_urlsafe(32))"`), set it in `PYTHON_API_TOKEN`, and use the same value in your `Authorization` header.

## API

### POST /analysis/facts

Request:

```json
{
  "ticker": "aapl"
}
```

Response:

```json
{
  "eps": { "...": "..." },
  "cashflow": { "...": "..." },
  "revenue": { "...": "..." }
}
```

Example:

```bash
curl -X POST http://localhost:8000/analysis/facts \
  -H "Authorization: Bearer local-dev-token" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"aapl"}'
```

### POST /analysis/insights

Request:

```json
{
  "ticker": "aapl",
  "useCache": true
}
```

Response:

```json
{
  "revenue": { "...": "..." },
  "cashflow": { "...": "..." },
  "debt": { "...": "..." },
  "stockinfo": []
}
```

Example:

```bash
curl -X POST http://localhost:8000/analysis/insights \
  -H "Authorization: Bearer local-dev-token" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"aapl","useCache":true}'
```
