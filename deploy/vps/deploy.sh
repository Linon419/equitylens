#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
ENV_FILE="$SCRIPT_DIR/.env"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy .env.example and fill every required value." >&2
  exit 1
fi

cd "$ROOT_DIR"

API_DOMAIN=$(sed -n 's/^API_DOMAIN=//p' "$ENV_FILE" | tail -n 1)
API_PORT=$(sed -n 's/^API_PORT=//p' "$ENV_FILE" | tail -n 1)
REVERSE_PROXY_MODE=$(sed -n 's/^REVERSE_PROXY_MODE=//p' "$ENV_FILE" | tail -n 1)
if [ -z "$API_DOMAIN" ]; then
  echo "API_DOMAIN is required." >&2
  exit 1
fi
API_PORT=${API_PORT:-18000}
REVERSE_PROXY_MODE=${REVERSE_PROXY_MODE:-caddy}

case "$REVERSE_PROXY_MODE" in
  caddy)
    PROFILE_ARGS="--profile caddy"
    READINESS_URL="https://$API_DOMAIN/api/v1/health/ready"
    ;;
  external)
    PROFILE_ARGS=""
    READINESS_URL="http://127.0.0.1:$API_PORT/api/v1/health/ready"
    ;;
  *)
    echo "REVERSE_PROXY_MODE must be caddy or external." >&2
    exit 1
    ;;
esac

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" $PROFILE_ARGS config >/dev/null
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" $PROFILE_ARGS build --pull
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" $PROFILE_ARGS up -d --remove-orphans

attempt=1
while [ "$attempt" -le 30 ]; do
  if curl --fail --silent --show-error "$READINESS_URL" >/dev/null; then
    echo "EquityLens API is ready at $READINESS_URL"
    exit 0
  fi
  sleep 2
  attempt=$((attempt + 1))
done

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=100 api worker caddy
echo "API readiness check timed out." >&2
exit 1
