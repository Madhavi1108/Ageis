"""Placeholder worker entrypoint.

Proves the docker-compose ``worker`` service shape (a long-running process
sharing the api image) without any real job-processing logic. Real job
consumption is orchestration-layer work for a later phase.
"""

from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger("aegis.worker_placeholder")


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    logger.info("worker placeholder started; no job-processing logic yet")
    while True:
        time.sleep(60)
        logger.info("worker placeholder heartbeat")


if __name__ == "__main__":
    main()
