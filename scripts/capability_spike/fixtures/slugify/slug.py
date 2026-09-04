"""Slug generation.

Known bug: slugify() does not strip punctuation, only lowercases and
replaces spaces with hyphens.
"""


def slugify(text: str) -> str:
    """Turn a title into a URL-safe slug: lowercase, hyphen-separated,
    punctuation removed."""
    # BUG: punctuation such as "!" and "?" is left in place.
    return text.lower().replace(" ", "-")
