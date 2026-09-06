"""Application configuration. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10.

Settings are validated eagerly at process start (``create_app()`` calls
``get_settings()`` before anything else) so a missing or malformed
environment variable fails fast with a clear error, rather than surfacing
lazily on first request.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_VALID_ENVIRONMENTS = {"dev", "test", "prod"}


class Settings(BaseSettings):
    """Process-wide configuration, sourced from environment variables / .env.

    All AEGIS-specific variables are prefixed ``AEGIS_`` (e.g. ``AEGIS_LOG_LEVEL``).
    ``extra="forbid"`` rejects unknown keys passed directly to the constructor
    (e.g. in tests); pydantic-settings does not extend that check to the
    process environment itself, so an unrecognized ``AEGIS_*`` env var is
    ignored rather than rejected -- other tools' env vars may share the
    prefix, and this avoids fail-fast being overly strict about that.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AEGIS_",
        extra="forbid",
        case_sensitive=False,
    )

    environment: str = Field(default="dev", description="dev | test | prod")
    log_level: str = Field(default="INFO")
    database_url: str = Field(default="sqlite:///./aegis.db")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    request_max_body_bytes: int = Field(default=1_000_000, gt=0)

    # Ingestion (Phase 3, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 11 / ADR-0012).
    ingestion_local_roots: list[str] = Field(
        default_factory=lambda: ["../test-repositories"]
    )
    ingestion_allowed_remote_hosts: list[str] = Field(
        default_factory=lambda: ["github.com"]
    )
    ingestion_max_repo_bytes: int = Field(default=500 * 1024 * 1024, gt=0)
    ingestion_max_files: int = Field(default=25_000, gt=0)
    ingestion_max_file_bytes: int = Field(default=2 * 1024 * 1024, gt=0)
    ingestion_max_history_depth: int = Field(default=500, gt=0)
    ingestion_default_clone_depth: int = Field(default=50, gt=0)
    ingestion_clone_timeout_s: int = Field(default=120, gt=0)
    artifacts_root: str = Field(default="./artifacts")

    # Task / issue ingestion (Phase 6, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14).
    # Issue text above this byte budget is truncated (not rejected), with the
    # original size recorded on the create response for provenance.
    task_max_description_bytes: int = Field(default=50_000, gt=0)
    task_max_title_chars: int = Field(default=200, gt=0)

    # Issue -> code mapping (Phase 7, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 15).
    # top_k: candidates returned; confidence_threshold: a candidate whose per-
    # candidate confidence is below this is dropped (nothing above it -> UNKNOWN,
    # i.e. an empty candidate list); graph_hops: k-hop radius for the graph-
    # proximity retriever; max_indexed_file_bytes: a source file larger than this
    # is skipped by the lexical FTS index (with provenance), never silently
    # truncated mid-token.
    mapping_top_k: int = Field(default=10, gt=0)
    mapping_confidence_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    mapping_graph_hops: int = Field(default=2, gt=0)
    mapping_max_indexed_file_bytes: int = Field(default=1_000_000, gt=0)

    # Impact analysis (Phase 8, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 16).
    # blast_radius_hops: reverse-graph BFS depth from each changed node;
    # max_regression_areas: cap on the ranked regression-area list.
    impact_blast_radius_hops: int = Field(default=3, gt=0)
    impact_max_regression_areas: int = Field(default=20, gt=0)

    # AI provider + planning (Phase 9, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 17,
    # ADR-0005, ADR-0019). ``ai_provider="none"`` skips the model entirely and uses
    # the deterministic rule-based fallback plan; ``"mock"`` is the CI default.
    # ``"claude"`` is real but only usable with RUN_LIVE_AI=1 + ANTHROPIC_API_KEY.
    ai_provider: str = Field(default="mock")
    ai_model: str = Field(default="claude-sonnet-5")
    ai_planning_timeout_s: float = Field(default=60.0, gt=0)
    ai_planning_max_tokens: int = Field(default=4000, gt=0)
    ai_max_retries: int = Field(default=2, ge=0)
    ai_retry_backoff_s: float = Field(default=0.5, ge=0.0)

    # Real patch generation (Phase 10, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 18,
    # ADR-0008). implementation_max_edit_ops: a model proposing more than this many
    # ops in one call fails loudly (IMPLEMENTATION_FAILED) rather than being
    # silently truncated -- an oversized edit set is treated as a scope problem,
    # not a size problem to paper over.
    ai_implementation_timeout_s: float = Field(default=90.0, gt=0)
    ai_implementation_max_tokens: int = Field(default=6000, gt=0)
    implementation_max_edit_ops: int = Field(default=25, gt=0)

    # Test generation (Phase 11, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 19).
    # testing_max_cases: a model proposing more than this many cases in one call
    # fails loudly rather than being silently truncated (same rationale as
    # implementation_max_edit_ops).
    ai_test_synthesis_timeout_s: float = Field(default=90.0, gt=0)
    ai_test_synthesis_max_tokens: int = Field(default=6000, gt=0)
    testing_max_cases: int = Field(default=25, gt=0)

    # Secure execution (Phase 12, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 20,
    # docs/EXECUTION_MODEL.md Section 5, ADR-0010). Defaults match the plan's
    # documented table; docker unavailable -> PARTIALLY_SUPPORTED, no host fallback.
    sandbox_image: str = Field(default="aegis-sandbox:py311")
    sandbox_cpus: float = Field(default=2.0, gt=0)
    sandbox_memory_mb: int = Field(default=2048, gt=0)
    sandbox_pids_limit: int = Field(default=512, gt=0)
    sandbox_nofile_limit: int = Field(default=4096, gt=0)
    sandbox_nproc_limit: int = Field(default=512, gt=0)
    sandbox_wall_clock_s: int = Field(default=600, gt=0)

    # Failure investigation (Phase 13, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 21).
    # code_slice_lines: lines of source context gathered around each traceback
    # frame for the evidence bundle.
    investigation_code_slice_lines: int = Field(default=6, gt=0)

    # Autonomous debugging & repair (Phase 14, docs/AEGIS_IMPLEMENTATION_PLAN.md
    # Section 22). The loop stops at max_iterations, at the wall-clock budget, on
    # a repeated failure signature, or when the marginal reduction in failing
    # tests falls below min_improvement.
    repair_max_iterations: int = Field(default=4, gt=0)
    repair_wall_clock_s: int = Field(default=900, gt=0)
    repair_min_improvement: int = Field(default=1, ge=0)
    ai_rca_timeout_s: float = Field(default=90.0, gt=0)
    ai_repair_timeout_s: float = Field(default=90.0, gt=0)
    ai_repair_max_tokens: int = Field(default=6000, gt=0)

    # Regression intelligence (Phase 15, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 23).
    # related_hops: graph distance from a changed node still counted RELATED;
    # centrality_decile: a covered file at/above this betweenness percentile is
    # classified REGRESSION (0.9 = top 10%).
    regression_related_hops: int = Field(default=2, gt=0)
    regression_centrality_decile: float = Field(default=0.9, ge=0.0, le=1.0)

    @field_validator("ai_provider")
    @classmethod
    def _valid_ai_provider(cls, v: str) -> str:
        allowed = {"mock", "claude", "openai", "local", "none"}
        if v not in allowed:
            raise ValueError(f"ai_provider must be one of {sorted(allowed)}, got {v!r}")
        return v

    @field_validator("ingestion_local_roots")
    @classmethod
    def _resolve_local_roots(cls, v: list[str]) -> list[str]:
        # Resolved once here so url_validator.validate_local_path can do a plain
        # containment check against already-absolute paths on both sides.
        return [str(Path(root).resolve()) for root in v]

    @field_validator("environment")
    @classmethod
    def _valid_environment(cls, v: str) -> str:
        if v not in _VALID_ENVIRONMENTS:
            raise ValueError(
                f"environment must be one of {sorted(_VALID_ENVIRONMENTS)}, got {v!r}"
            )
        return v

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, v: str) -> str:
        upper = v.upper()
        if upper not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"log_level must be one of {sorted(_VALID_LOG_LEVELS)}, got {v!r}"
            )
        return upper


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton (constructed once, cached)."""
    return Settings()
