"""Repository intelligence: deterministic Python static analysis (Phase 4).

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 12. No AI/LLM involvement -- the
"Repository Analyst" agent is deterministic AST analysis (docs/AI_AGENT_DESIGN.md
Section 2). Kept separate from app/repository/ (Phase 2's data-access layer), mirroring
app/ingestion/'s split: this package holds business logic that *uses* the data-access
repositories, not another data-access layer itself.
"""
