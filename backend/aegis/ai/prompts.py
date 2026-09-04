"""Structured prompt assembly. See docs/AI_AGENT_DESIGN.md Section 8:
instruction body is static; untrusted content (issue text, repo code) only
ever goes into clearly delimited data blocks, never concatenated into the
instruction itself.

MockProvider does not read these (it looks up canned/fallback responses by
task_key) but a real provider (ClaudeProvider/OpenAIProvider) would send the
rendered prompt -- rendering it here now means the contract is real from day
one, even though Phase 1 does not exercise a live model by default.
"""

from __future__ import annotations

PLANNING_SCHEMA_HINT = """{
  "problem_interpretation": str, "assumptions": [str], "files_to_inspect": [str],
  "files_to_modify": [str], "symbols_to_modify": [str], "dependencies": [str],
  "steps": [{"id": str, "description": str, "test_intent": str, "evidence_refs": [str]}],
  "test_strategy": {}, "expected_behavior": str, "regression_risks": [str],
  "rollback_strategy": str, "source": "AI" | "RULE_BASED_FALLBACK",
  "confidence": {"value": float 0..1, "basis": "FACT"|"INFERENCE"|"HYPOTHESIS"|"RECOMMENDATION"|"UNKNOWN"},
  "evidence": [{"kind": str, "ref": str, "detail": str}]
}"""


def render_planning_prompt(*, task_text: str, candidates: list[str]) -> str:
    return (
        "You are the AEGIS Planning Agent. Produce a structured engineering plan.\n"
        'If you cannot determine something, use an empty list or "UNKNOWN" -- do not guess.\n\n'
        "<issue>\n" + task_text + "\n</issue>\n\n"
        "<candidate_files>\n" + "\n".join(candidates) + "\n</candidate_files>\n\n"
        "Return ONLY JSON matching this schema:\n" + PLANNING_SCHEMA_HINT
    )
