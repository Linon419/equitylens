import pytest

from app.jobs.state import next_state


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("queued", "downloading"),
        ("downloading", "parsing"),
        ("parsing", "analyzing"),
        ("analyzing", "verifying"),
        ("verifying", "localizing"),
        ("localizing", "completed"),
    ],
)
def test_pipeline_allows_forward_transitions(current: str, target: str) -> None:
    assert next_state(current, target) == target


def test_pipeline_rejects_skipped_or_backward_transitions() -> None:
    with pytest.raises(ValueError):
        next_state("queued", "analyzing")
    with pytest.raises(ValueError):
        next_state("verifying", "parsing")
