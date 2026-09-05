"""AppError subclasses specific to the code graph. Mirrors
app/analysis/errors.py's shape exactly.
"""
from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class GraphNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "GRAPH_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class GraphNodeNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "GRAPH_NODE_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )
