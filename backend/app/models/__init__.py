"""SQLAlchemy models. Import all model modules here so Base.metadata sees
every table (Alembic autogenerate and create_all both rely on this)."""

from __future__ import annotations

from app.models.artifact import Artifact
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.code_mapping import CodeMapping
from app.models.dependency import Dependency
from app.models.engineering_plan import EngineeringPlan
from app.models.graph_edge import GraphEdge
from app.models.graph_node import GraphNode
from app.models.impact_analysis import ImpactAnalysis
from app.models.implementation import Implementation, Patch
from app.models.issue import Issue
from app.models.job import Job
from app.models.repository import Repository
from app.models.repository_analysis import RepositoryAnalysis
from app.models.repository_file import RepositoryFile
from app.models.repository_symbol import RepositorySymbol
from app.models.snapshot import RepositorySnapshot
from app.models.task import Task
from app.models.task_step import TaskStep

__all__ = [
    "Base",
    "Job",
    "AuditLog",
    "Repository",
    "RepositorySnapshot",
    "RepositoryFile",
    "Artifact",
    "RepositorySymbol",
    "Dependency",
    "RepositoryAnalysis",
    "GraphNode",
    "GraphEdge",
    "Issue",
    "Task",
    "TaskStep",
    "CodeMapping",
    "ImpactAnalysis",
    "EngineeringPlan",
    "Implementation",
    "Patch",
]
