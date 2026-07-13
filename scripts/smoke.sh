#!/usr/bin/env bash
set -euo pipefail

WEB_BASE_URL="${WEB_BASE_URL:-http://localhost:3000}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

web_response="$(curl --fail --silent --show-error "${WEB_BASE_URL}/api/health")"
api_response="$(curl --fail --silent --show-error "${API_BASE_URL}/api/v1/health")"
curl --fail --silent --show-error --output /dev/null \
  "${WEB_BASE_URL}/en-US/dashboard"
search_response="$(curl --fail --silent --show-error \
  "${WEB_BASE_URL}/api/research/companies/search?q=AAPL")"

test "${web_response}" = '{"status":"ok"}'
test "${api_response}" = '{"status":"ok"}'
case "${search_response}" in
  *'"symbol":"AAPL"'*) ;;
  *)
    echo "Company search smoke check did not return AAPL" >&2
    exit 1
    ;;
esac

echo "Health, dashboard, and company search checks passed for ${WEB_BASE_URL} and ${API_BASE_URL}"
