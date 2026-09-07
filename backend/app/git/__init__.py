"""Local Git intelligence (Phase 19, docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 27, ADR-0014).

Read-only history / blame / churn over a real Git repository via GitPython --
never a ``git`` subprocess with interpolated arguments. The snapshot workspace
is a files-only copy with no ``.git`` (app/ingestion/workspace.py), so
``repo_access.open_repo`` reaches a real repo another way: the LOCAL origin
path, or a fresh shallow re-clone for a GITHUB repo. When neither is possible
the callers return a structured "unavailable" result, not an error.

Pure, no network beyond the optional re-clone, no AI.
"""

from __future__ import annotations
