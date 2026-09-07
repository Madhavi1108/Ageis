"""Worker entrypoint shim.

Kept for the docker-compose ``worker`` service and any scripts that import
``app.worker_placeholder:main``. The real job-processing loop now lives in
``app.orchestration.worker`` (Phase 21).
"""

from __future__ import annotations

from app.orchestration.worker import main

__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover
    main()
