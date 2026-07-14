COMPANY_INTELLIGENCE_STATES = (
    "queued",
    "downloading",
    "parsing",
    "analyzing",
    "verifying",
    "localizing",
    "completed",
)
SUPPLY_CHAIN_GRAPH_STATES = (
    "queued",
    "collecting",
    "extracting",
    "resolving",
    "verifying",
    "localizing",
    "completed",
)
JOB_STATES = {
    "company_intelligence": COMPANY_INTELLIGENCE_STATES,
    "supply_chain_graph": SUPPLY_CHAIN_GRAPH_STATES,
}


def states_for(job_type: str) -> tuple[str, ...]:
    try:
        return JOB_STATES[job_type]
    except KeyError as error:
        raise ValueError(f"unknown job type: {job_type}") from error


def next_state(job_type: str, current: str, target: str) -> str:
    states = states_for(job_type)
    try:
        current_index = states.index(current)
        target_index = states.index(target)
    except ValueError as error:
        raise ValueError("unknown pipeline state") from error
    if target_index != current_index + 1:
        raise ValueError(f"invalid pipeline transition: {current} -> {target}")
    return target


def has_reached(job_type: str, current: str, target: str) -> bool:
    if current == "failed":
        return False
    states = states_for(job_type)
    try:
        return states.index(current) >= states.index(target)
    except ValueError as error:
        raise ValueError("unknown pipeline state") from error


def prior_state(job_type: str, current_step: str) -> str:
    states = states_for(job_type)
    try:
        index = states.index(current_step)
    except ValueError as error:
        raise ValueError("unknown pipeline state") from error
    return states[max(0, index - 1)]
