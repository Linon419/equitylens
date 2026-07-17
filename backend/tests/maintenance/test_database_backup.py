from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.maintenance.database_backup import BACKUP_PREFIX, upload_backup


def test_uploads_private_backup_and_removes_expired_objects() -> None:
    now = datetime(2026, 7, 17, tzinfo=UTC)
    recent = SimpleNamespace(
        url="https://blob.example/recent",
        uploaded_at=now - timedelta(days=2),
    )
    expired = SimpleNamespace(
        url="https://blob.example/expired",
        uploaded_at=now - timedelta(days=31),
    )
    uploaded = SimpleNamespace(pathname=f"{BACKUP_PREFIX}backup.dump")

    with (
        patch("app.maintenance.database_backup.put", return_value=uploaded) as put,
        patch(
            "app.maintenance.database_backup.iter_objects",
            return_value=iter([recent, expired]),
        ),
        patch("app.maintenance.database_backup.delete") as delete,
    ):
        result = upload_backup(uploaded.pathname, b"database", "token", now=now)

    assert result == (uploaded.pathname, 1)
    put.assert_called_once_with(
        uploaded.pathname,
        b"database",
        access="private",
        content_type="application/octet-stream",
        token="token",
        multipart=True,
    )
    delete.assert_called_once_with([expired.url], token="token")


@pytest.mark.parametrize(
    ("pathname", "body"),
    [("other/backup.dump", b"database"), (f"{BACKUP_PREFIX}empty.dump", b"")],
)
def test_rejects_unsafe_or_empty_backups(pathname: str, body: bytes) -> None:
    with pytest.raises(ValueError):
        upload_backup(pathname, body, "token")
