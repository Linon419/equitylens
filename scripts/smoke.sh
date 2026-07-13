#!/usr/bin/env bash
set -euo pipefail

WEB_BASE_URL="${WEB_BASE_URL:-http://localhost:3000}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

web_response="$(curl --fail --silent --show-error "${WEB_BASE_URL}/api/health")"
api_response="$(curl --fail --silent --show-error "${API_BASE_URL}/api/v1/health/live")"

test "${web_response}" = '{"status":"ok"}'
test "${api_response}" = '{"status":"ok"}'

echo "Smoke checks passed for ${WEB_BASE_URL} and ${API_BASE_URL}"
