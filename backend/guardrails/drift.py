"""Drift / manipulation-resistance checks. Interface only for now."""


def check_drift(transcript: list[dict[str, str]]) -> bool:
    """Return True if the conversation shows signs of prompt-injection or
    persona drift. TODO: implement real detection (heuristics or a
    classifier call) — always returns False for now."""
    return False
