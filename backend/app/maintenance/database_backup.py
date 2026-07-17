import os
import sys
from datetime import UTC, datetime, timedelta

from vercel.blob import delete, iter_objects, put

BACKUP_PREFIX = "database-backups/"
OFFSITE_RETENTION_DAYS = 30


def upload_backup(
    pathname: str,
    body: bytes,
    token: str,
    *,
    now: datetime | None = None,
) -> tuple[str, int]:
    if not pathname.startswith(BACKUP_PREFIX):
        raise ValueError("Database backup path must use the protected prefix")
    if not body:
        raise ValueError("Database backup is empty")

    uploaded = put(
        pathname,
        body,
        access="private",
        content_type="application/octet-stream",
        token=token,
        multipart=True,
    )
    cutoff = (now or datetime.now(UTC)) - timedelta(days=OFFSITE_RETENTION_DAYS)
    expired = [
        item.url
        for item in iter_objects(prefix=BACKUP_PREFIX, token=token)
        if item.uploaded_at < cutoff
    ]
    if expired:
        delete(expired, token=token)
    return uploaded.pathname, len(expired)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.maintenance.database_backup PATHNAME")
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise SystemExit("BLOB_READ_WRITE_TOKEN is required")
    pathname, deleted = upload_backup(
        sys.argv[1],
        sys.stdin.buffer.read(),
        token,
    )
    print(f"Uploaded {pathname}; removed {deleted} expired backup(s)")


if __name__ == "__main__":
    main()
