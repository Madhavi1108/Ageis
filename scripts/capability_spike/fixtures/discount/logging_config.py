"""Unrelated logging setup (distractor for the localization spike)."""

import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level)
