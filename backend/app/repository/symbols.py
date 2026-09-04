"""Repository pattern for RepositorySymbol data access. Mirrors FileRepository's shape."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.repository_symbol import RepositorySymbol


class SymbolRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_create(self, snapshot_id: str, symbols: list) -> list[RepositorySymbol]:
        rows = [
            RepositorySymbol(
                snapshot_id=snapshot_id,
                file_id=s.file_id,
                symbol_id=s.symbol_id,
                kind=s.kind,
                qualname=s.qualname,
                signature=s.signature,
                lineno=s.lineno,
                end_lineno=s.end_lineno,
                decorators=s.decorators,
                docstring=s.docstring,
                is_exported=s.is_exported,
            )
            for s in symbols
        ]
        self._session.add_all(rows)
        self._session.commit()
        return rows

    def replace_for_snapshot(
        self, snapshot_id: str, symbols: list
    ) -> list[RepositorySymbol]:
        self._session.execute(
            delete(RepositorySymbol).where(RepositorySymbol.snapshot_id == snapshot_id)
        )
        self._session.commit()
        return self.bulk_create(snapshot_id, symbols)

    def list_for_snapshot(
        self, snapshot_id: str, *, kind: str | None = None, limit: int = 10_000
    ) -> list[RepositorySymbol]:
        stmt = select(RepositorySymbol).where(
            RepositorySymbol.snapshot_id == snapshot_id
        )
        if kind is not None:
            stmt = stmt.where(RepositorySymbol.kind == kind)
        stmt = stmt.order_by(RepositorySymbol.symbol_id).limit(limit)
        return list(self._session.execute(stmt).scalars().all())
