from datetime import UTC, datetime

from app.providers.contracts import JobState, UploadIntent


def test_upload_intent_has_stable_values() -> None:
    intent = UploadIntent(
        object_key="users/1/documents/report.pdf",
        upload_url="https://uploads.example.com/report.pdf",
        headers={"content-type": "application/pdf"},
        expires_at=datetime(2026, 7, 13, tzinfo=UTC),
    )

    assert intent.object_key.endswith("report.pdf")
    assert intent.headers == {"content-type": "application/pdf"}


def test_job_state_has_stable_wire_values() -> None:
    assert [state.value for state in JobState] == [
        "queued",
        "downloading",
        "parsing",
        "analyzing",
        "verifying",
        "localizing",
        "completed",
        "failed",
    ]
