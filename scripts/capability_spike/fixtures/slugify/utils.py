"""Unrelated helper module (distractor for the localization spike)."""


def truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len]
