from datetime import UTC, datetime

from app.quota.identity import sign_guest_assertion

GUEST_ONE = "11111111-1111-4111-8111-111111111111"
GUEST_TWO = "22222222-2222-4222-8222-222222222222"


def guest_headers(guest_id: str, ip_hash: str = "a" * 64) -> dict[str, str]:
    return {
        "x-guest-assertion": sign_guest_assertion(
            guest_id=guest_id,
            ip_hash=ip_hash,
            secret="g" * 32,
            now=datetime.now(UTC),
        )
    }


def test_sync_job_status_and_quota_are_guest_scoped(phase_2_api) -> None:
    headers = guest_headers(GUEST_ONE)

    accepted = phase_2_api.client.post(
        "/api/v1/companies/AAPL/sync",
        headers=headers,
    )

    assert accepted.status_code == 202
    payload = accepted.json()
    assert payload["status"] == "accepted"
    assert payload["job"]["state"] == "queued"
    assert payload["quota"]["remaining"] == 1
    job_id = payload["job"]["id"]

    duplicate = phase_2_api.client.post(
        "/api/v1/companies/AAPL/sync",
        headers=headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "active_job"
    assert duplicate.json()["quota"]["remaining"] == 1

    own_job = phase_2_api.client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert own_job.status_code == 200
    other_job = phase_2_api.client.get(
        f"/api/v1/jobs/{job_id}",
        headers=guest_headers(GUEST_TWO, "b" * 64),
    )
    assert other_job.status_code == 404
    assert other_job.json()["code"] == "JOB_NOT_FOUND"

    quota = phase_2_api.client.get("/api/v1/agent-quota", headers=headers)
    assert quota.status_code == 200
    assert quota.json()["remaining"] == 1


def test_dispatch_failure_can_retry_without_consuming_quota(phase_2_api) -> None:
    headers = guest_headers(GUEST_ONE)
    phase_2_api.jobs.fail = True
    accepted = phase_2_api.client.post(
        "/api/v1/companies/AAPL/sync",
        headers=headers,
    )
    job_id = accepted.json()["job"]["id"]
    assert accepted.json()["job"]["error_code"] == "JOB_DISPATCH_FAILED"

    phase_2_api.jobs.fail = False
    retried = phase_2_api.client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers=headers,
    )

    assert retried.status_code == 200
    assert retried.json()["attempt_count"] == 1
    assert retried.json()["provider_run_id"].startswith("fake:")
    quota = phase_2_api.client.get("/api/v1/agent-quota", headers=headers)
    assert quota.json()["used"] == 1


def test_agent_endpoints_require_guest_assertion_or_user_token(phase_2_api) -> None:
    response = phase_2_api.client.get("/api/v1/agent-quota")

    assert response.status_code == 401
    assert response.json()["code"] == "GUEST_ASSERTION_REQUIRED"
