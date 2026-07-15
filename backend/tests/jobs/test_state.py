import pytest

from app.jobs.state import has_reached, next_state, prior_state, states_for


def test_supply_chain_graph_state_order() -> None:
    assert states_for("supply_chain_graph") == (
        "queued",
        "collecting",
        "extracting",
        "resolving",
        "verifying",
        "localizing",
        "completed",
    )


def test_company_intelligence_state_order_is_unchanged() -> None:
    assert states_for("company_intelligence") == (
        "queued",
        "downloading",
        "parsing",
        "indexing",
        "analyzing",
        "verifying",
        "localizing",
        "completed",
    )


def test_filing_index_state_order() -> None:
    assert states_for("filing_index") == (
        "queued",
        "chunking",
        "embedding",
        "indexing",
        "completed",
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("queued", "downloading"),
        ("downloading", "parsing"),
        ("parsing", "indexing"),
        ("indexing", "analyzing"),
        ("analyzing", "verifying"),
        ("verifying", "localizing"),
        ("localizing", "completed"),
    ],
)
def test_pipeline_allows_forward_transitions(current: str, target: str) -> None:
    assert next_state("company_intelligence", current, target) == target


def test_pipeline_rejects_skipped_or_backward_transitions() -> None:
    with pytest.raises(ValueError):
        next_state("company_intelligence", "queued", "analyzing")
    with pytest.raises(ValueError):
        next_state("company_intelligence", "verifying", "parsing")


def test_graph_rejects_company_intelligence_states() -> None:
    with pytest.raises(ValueError):
        next_state("supply_chain_graph", "queued", "downloading")
    with pytest.raises(ValueError):
        has_reached("supply_chain_graph", "extracting", "analyzing")


def test_retry_prior_state_is_scoped_by_job_type() -> None:
    assert prior_state("supply_chain_graph", "resolving") == "extracting"
    assert prior_state("company_intelligence", "verifying") == "analyzing"
    assert prior_state("supply_chain_graph", "collecting") == "queued"


def test_unknown_job_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown job type"):
        states_for("unknown")
