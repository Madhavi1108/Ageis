"""Parse a bulk-import workbook and create repositories + tasks through the
same domain services the API uses (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 31).

Import is validation-parity by construction: repository rows go through
app/services/repositories.py::create_repository and task rows through
app/services/tasks.py::create_task -- the exact functions
POST /repositories and POST /tasks call. Per-row failures are collected into
ImportResult.errors; nothing is silently skipped and one bad row never aborts
the rest.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

from openpyxl import load_workbook
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.reporting.errors import WorkbookParseError, WorkbookSchemaError
from app.reporting.workbook_schema import (
    REPOSITORIES_COLUMNS,
    REPOSITORIES_SHEET,
    TASKS_IMPORT_COLUMNS,
    TASKS_SHEET,
    all_columns,
    required_columns,
)
from app.repository.repositories import RepositoryRepository
from app.schemas.report import ImportResult, ImportRowError
from app.schemas.repository import RepositoryCreateRequest
from app.schemas.task import IssueAnalysisInput, TaskCreate
from app.services import repositories as repositories_service
from app.services import tasks as tasks_service


@dataclass
class SheetRows:
    name: str
    headers: list[str]
    rows: list[dict[str, Any]] = field(default_factory=list)
    # 1-based worksheet row number for each entry in ``rows`` (row 1 is headers)
    row_numbers: list[int] = field(default_factory=list)


@dataclass
class ParsedImport:
    repositories: SheetRows
    tasks: SheetRows


def _cell_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _read_sheet(wb: Any, name: str, columns: list[tuple[str, bool]]) -> SheetRows:
    if name not in wb.sheetnames:
        raise WorkbookSchemaError(
            f"workbook is missing the required sheet {name!r}",
            details={"missing_sheet": name, "found_sheets": list(wb.sheetnames)},
        )
    ws = wb[name]
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        header_row = ()
    headers = [str(h).strip() if h is not None else "" for h in header_row]

    missing = [c for c in required_columns(columns) if c not in headers]
    if missing:
        raise WorkbookSchemaError(
            f"sheet {name!r} is missing required column(s): {', '.join(missing)}",
            details={"sheet": name, "missing_columns": missing, "headers": headers},
        )

    known = set(all_columns(columns))
    out = SheetRows(name=name, headers=headers)
    for offset, raw in enumerate(rows_iter, start=2):
        record = {
            headers[i]: raw[i]
            for i in range(min(len(headers), len(raw)))
            if headers[i] in known
        }
        if all(_cell_str(v) is None for v in record.values()):
            continue  # skip fully blank rows
        out.rows.append(record)
        out.row_numbers.append(offset)
    return out


def parse_import_workbook(data: bytes) -> ParsedImport:
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 -- openpyxl raises a grab-bag of types
        raise WorkbookParseError(f"could not read the workbook: {exc}") from exc

    try:
        repositories = _read_sheet(wb, REPOSITORIES_SHEET, REPOSITORIES_COLUMNS)
        tasks = _read_sheet(wb, TASKS_SHEET, TASKS_IMPORT_COLUMNS)
    finally:
        wb.close()
    return ParsedImport(repositories=repositories, tasks=tasks)


def _split_globs(value: Any) -> list[str] | None:
    text = _cell_str(value)
    if not text:
        return None
    parts = [p.strip() for p in text.replace(",", "\n").splitlines()]
    globs = [p for p in parts if p]
    return globs or None


def _row_error(sheet: str, row: int, exc: Exception) -> ImportRowError:
    if isinstance(exc, AppError):
        return ImportRowError(
            sheet=sheet,
            row=row,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
    if isinstance(exc, ValidationError):
        return ImportRowError(
            sheet=sheet,
            row=row,
            code="VALIDATION_ERROR",
            message="row failed schema validation",
            details={
                "errors": [
                    {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                    for e in exc.errors()
                ]
            },
        )
    return ImportRowError(
        sheet=sheet,
        row=row,
        code="ROW_ERROR",
        message=str(exc) or exc.__class__.__name__,
    )


def run_import(db: Session, *, settings: Settings, data: bytes) -> ImportResult:
    parsed = parse_import_workbook(data)
    result = ImportResult(repositories_created=0, tasks_created=0)

    # url_or_path -> repository_id, seeded with anything already in the DB so a
    # task row can reference a pre-existing repo.
    known_repos: dict[str, str] = {}
    repo_repo = RepositoryRepository(db)

    for record, row_no in zip(
        parsed.repositories.rows, parsed.repositories.row_numbers
    ):
        try:
            body = RepositoryCreateRequest(
                source_type=_cell_str(record.get("source_type")),  # type: ignore[arg-type]
                url_or_path=_cell_str(record.get("url_or_path")) or "",
                name=_cell_str(record.get("name")),
                owner=_cell_str(record.get("owner")),
                default_branch=_cell_str(record.get("default_branch")),
            )
            pre_existing = (
                repo_repo.get_by_source(body.source_type, body.url_or_path) is not None
            )
            repo = repositories_service.create_repository(
                db, settings=settings, body=body
            )
            known_repos[repo.url_or_path] = repo.id
            result.repository_ids.append(repo.id)
            if not pre_existing:
                result.repositories_created += 1
        except Exception as exc:  # noqa: BLE001 -- reported per row, never fatal
            result.errors.append(_row_error(REPOSITORIES_SHEET, row_no, exc))

    for record, row_no in zip(parsed.tasks.rows, parsed.tasks.row_numbers):
        try:
            ref = _cell_str(record.get("repository_url_or_path"))
            repo_id = known_repos.get(ref or "")
            if repo_id is None and ref:
                existing = repo_repo.get_by_source(
                    "LOCAL", ref
                ) or repo_repo.get_by_source("GITHUB", ref)
                repo_id = existing.id if existing else None
            if repo_id is None:
                raise WorkbookSchemaError(
                    f"task row references unknown repository {ref!r}",
                    details={"repository_url_or_path": ref},
                )

            issue_title = _cell_str(record.get("issue_title"))
            issue_body = _cell_str(record.get("issue_body"))
            issue = None
            text = _cell_str(record.get("text"))
            if issue_title or issue_body:
                issue = IssueAnalysisInput(
                    source="EXCEL",
                    external_ref=_cell_str(record.get("issue_external_ref")),
                    title=issue_title or "",
                    body=issue_body or "",
                )
                text = None

            payload = TaskCreate(
                repository_id=repo_id,
                text=text,
                issue=issue,
                title=_cell_str(record.get("title")),
                task_type=_cell_str(record.get("task_type")),  # type: ignore[arg-type]
                priority=_cell_str(record.get("priority")) or "NORMAL",  # type: ignore[arg-type]
                allowed_paths=_split_globs(record.get("allowed_paths")),
                created_by=_cell_str(record.get("created_by")),
            )
            created = tasks_service.create_task(db, settings=settings, payload=payload)
            result.task_ids.append(created.task.id)
            result.tasks_created += 1
        except Exception as exc:  # noqa: BLE001 -- reported per row, never fatal
            result.errors.append(_row_error(TASKS_SHEET, row_no, exc))

    return result
