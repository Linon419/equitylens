PIPELINE_STATES = (
    "queued",
    "downloading",
    "parsing",
    "analyzing",
    "verifying",
    "localizing",
    "completed",
)


def next_state(current: str, target: str) -> str:
    try:
        current_index = PIPELINE_STATES.index(current)
        target_index = PIPELINE_STATES.index(target)
    except ValueError as error:
        raise ValueError("unknown pipeline state") from error
    if target_index != current_index + 1:
        raise ValueError(f"invalid pipeline transition: {current} -> {target}")
    return target


def has_reached(current: str, target: str) -> bool:
    if current == "failed":
        return False
    try:
        return PIPELINE_STATES.index(current) >= PIPELINE_STATES.index(target)
    except ValueError as error:
        raise ValueError("unknown pipeline state") from error
