#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_PATH="${ENV_PATH:-${REPO_ROOT}/.env}"

if [[ -f "${ENV_PATH}" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ENV_PATH}"
  set +a
fi

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

if [[ -z "${PYTHON_API_TOKEN:-}" ]]; then
  echo "PYTHON_API_TOKEN is required for the smoke test." >&2
  exit 1
fi

echo "Running smoke tests against ${API_BASE_URL}"

curl -sS -X POST "${API_BASE_URL}/analysis/facts" \
  -H "Authorization: Bearer ${PYTHON_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"aapl"}'
echo

curl -sS -X POST "${API_BASE_URL}/analysis/insights" \
  -H "Authorization: Bearer ${PYTHON_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"aapl","useCache":true}'
echo
