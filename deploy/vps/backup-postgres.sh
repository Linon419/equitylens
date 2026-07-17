#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
ENV_FILE="$SCRIPT_DIR/.env"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
BACKUP_DIR=${BACKUP_DIR:-/var/backups/equitylens/postgres}
LOCAL_RETENTION_DAYS=${LOCAL_RETENTION_DAYS:-7}

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE." >&2
  exit 1
fi

POSTGRES_DB=$(sed -n 's/^POSTGRES_DB=//p' "$ENV_FILE" | tail -n 1)
POSTGRES_USER=$(sed -n 's/^POSTGRES_USER=//p' "$ENV_FILE" | tail -n 1)
if [ -z "$POSTGRES_DB" ] || [ -z "$POSTGRES_USER" ]; then
  echo "POSTGRES_DB and POSTGRES_USER are required." >&2
  exit 1
fi
case "$LOCAL_RETENTION_DAYS" in
  ''|*[!0-9]*)
    echo "LOCAL_RETENTION_DAYS must be a positive integer." >&2
    exit 1
    ;;
esac
if [ "$LOCAL_RETENTION_DAYS" -lt 1 ]; then
  echo "LOCAL_RETENTION_DAYS must be at least 1." >&2
  exit 1
fi

umask 077
mkdir -p "$BACKUP_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
NAME="equitylens-$STAMP.dump"
TEMP_FILE="$BACKUP_DIR/$NAME.tmp"
BACKUP_FILE="$BACKUP_DIR/$NAME"
trap 'rm -f "$TEMP_FILE"' EXIT INT TERM

cd "$ROOT_DIR"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --format custom --compress 9 --no-owner --no-privileges > "$TEMP_FILE"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
  pg_restore --list < "$TEMP_FILE" >/dev/null
mv "$TEMP_FILE" "$BACKUP_FILE"
trap - EXIT INT TERM

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api \
  python -m app.maintenance.database_backup "database-backups/$NAME" < "$BACKUP_FILE"
find "$BACKUP_DIR" -type f -name 'equitylens-*.dump' \
  -mtime "+$((LOCAL_RETENTION_DAYS - 1))" -delete
echo "Database backup verified at $BACKUP_FILE"
