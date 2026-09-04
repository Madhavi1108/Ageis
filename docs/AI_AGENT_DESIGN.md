# AEGIS AI & Agent Design

Traceability: Specification §3.8, §4, §5, §20, §21. Phase 0 deliverable (Spec §46 items 7, 8, 9).
Companion to `AEGIS_IMPLEMENTATION_PLAN.md` §3.3, §4.5–§4.7, §4.13; `ADR-0004`, `ADR-0005`,
`ADR-0019`.

Status: Accepted — 2026-09-04.

---

## 1. Design principle

AEGIS is a typed engineering pipeline, not a chat loop (Spec §52). Seven fixed agents, one central
Orchestrator, communication only via Pydantic schemas. Agents do not call each other or the model
directly for control flow — the Orchestrator sequences them and each agent uses the `AIProvider`
only to fill a specific schema.

---

## 2. The seven agents (Spec §5)

| Agent | Consumes | Produces | Uses AI? | Failure behaviour |
|---|---|---|---|---|
| **Repository Analyst** | `RepositorySnapshot` | `RepositoryAnalysis` / `RepositoryContext` | No (deterministic AST) | unparseable file recorded; analysis continues |
| **Planning** | `RepositoryContext` slice, `IssueCodeMapping`, `ImpactAnalysis`, memory hits | `EngineeringPlan` + `PlanValidation` | Yes (frontier) | invalid schema -> 1 repair round -> `FAILED`; no provider -> rule-based fallback plan (`source=RULE_BASED_FALLBACK`, LOW confidence) |
| **Implementation** | approved `EngineeringPlan` | `ImplementationResult` (+ `Patch`) | Yes (frontier) — emits structured edit ops only | ambiguous/missing anchor -> stop loudly; out-of-scope write -> blocked + event |
| **Testing** | plan, changed symbols, framework profile | `TestGeneration` (+ `TestCase`s) | Yes (frontier) | uncollectable test -> `INVALID` + 1 repair round; never edits unrelated tests |
| **Debugging** | `FailureAnalysis`, diff, graph, history, memory | `RootCauseAnalysis`, `RepairProposal`, `RepairAttempt`s | Yes (frontier for RCA) + deterministic heuristics | bounded loop; auto-revert on worse; safe stop with evidence |
| **Code Review** | `Patch`, `TestCase`s, static-tool output | `ReviewFinding[]` / `ReviewReport` | Yes (frontier) + static analyzers | AI finding without a line -> downgraded to `INFO` |
| **Verification** | plan, diff, executions, review, scores | `VerificationResult` + engineering trace | No (deterministic checklist; may use AI only to phrase the trace) | any mandatory criterion fails -> `NOT_VERIFIED` |

The **Orchestrator** owns workflow state, budgets (calls, cost, wall-clock), retries, checkpoints,
and the HITL policy. **Engineering Memory** is read before mapping/planning/RCA and written once at
a terminal state.

---

## 3. `AIProvider` abstraction (Spec §3.8)

```python
class AIProvider(Protocol):
    name: str
    def complete(self, *, template: str, variables: dict, schema: type[BaseModel],
                 tier: Literal["cheap", "frontier"], timeout_s: float,
                 max_tokens: int, temperature: float = 0.0) -> Validated: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...   # optional; may raise NotSupported
```

Implementations: `ClaudeProvider`, `OpenAIProvider`, `LocalProvider`, `MockProvider`
(deterministic, canned-by-prompt-hash — the CI default).

Every implementation provides:

- **Structured prompt assembly** from named templates + a variables dict. Untrusted content
  (repo code, issue text) is inserted only into clearly delimited data fields, never into the
  instruction body.
- **Schema-constrained output**: the model is asked for JSON matching `schema`; the response is
  validated by `ai/schema_guard.py`.
- **One repair round**: on invalid output, a single follow-up call quoting the validation error;
  still invalid -> raise `AIOutputInvalid` -> stage `FAILED` (no silent best-effort).
- **Retries** with exponential backoff on transport / 5xx / rate-limit, capped.
- **Per-call timeout**; **token/context budgeting** with deterministic truncation + provenance.
- **Redacted logging**: provider, model id, params, token counts, latency, and a digest of any
  untrusted prompt segment — never the raw body.
- **Config-selected**: absence of a real provider still yields a working pipeline (rule-based
  fallbacks, lower confidence).

---

## 4. Model routing (`ADR-0019`, Spec §-cost)

| Tier | Stages | Why |
|---|---|---|
| `cheap` | task normalization, `task_type` classification, lexical/graph candidate re-ranking, test-collection triage, summarization, trace phrasing | high volume, low reasoning depth |
| `frontier` | engineering planning, implementation edit-ops, test synthesis, root-cause analysis, code review | correctness-critical reasoning |

Routing is per-stage config, logged with token + cost accounting. The repair loop's frontier calls
are additionally bounded by the Phase 14 iteration and wall-clock budgets. Levers when cost
regresses: push stages down a tier, raise context-windowing aggressiveness, lower the repair cap,
enable prompt caching, enable the marginal-improvement early-exit (`COST_MODEL.md` §5).

---

## 5. Hallucination control (Spec §21)

- Every AI conclusion carries a label: `FACT` / `INFERENCE` / `HYPOTHESIS` / `RECOMMENDATION`.
- Missing information -> `UNKNOWN`. Weak evidence -> `LOW CONFIDENCE`.
- A `FACT` must reference >= 1 `Evidence` item AEGIS can independently re-check.
- Sandbox execution results override AI assertions, always.
- The Debugging agent must never invent a failure cause: RCA output separates observed FACTs from
  INFERENCEs from HYPOTHESEs, each with evidence.
- AI confidence is recorded but never substitutes for verification.

---

## 6. Shared schema primitives

```python
class Evidence(BaseModel):
    kind: Literal["file", "symbol", "line_range", "test", "commit", "dependency", "execution"]
    ref: str          # path, symbol_id, "path:start-end", test id, sha, package, execution id
    detail: str       # one line: what this evidence shows

class Confidence(BaseModel):
    value: float                      # 0..1
    basis: Literal["FACT", "INFERENCE", "HYPOTHESIS", "RECOMMENDATION", "UNKNOWN"]

class AgentError(BaseModel):
    code: str
    message: str
    recoverable: bool
    evidence: list[Evidence] = []
```

Every AI output schema below includes `confidence: Confidence`, `evidence: list[Evidence]`, and an
optional `error: AgentError | None`.

---

## 7. The 18 AI output schemas (Spec §20) — field sketch

| Schema | Key fields (beyond `confidence`, `evidence`, `error`) |
|---|---|
| `RepositoryAnalysis` | `entry_points[]`, `test_framework?`, `test_command?`, `package_manager?`, `build_backend?`, `symbol_count`, `unknowns[]` |
| `IssueAnalysis` | `task_type`, `summary`, `explicit_files[]`, `explicit_symbols[]`, `acceptance_hints[]`, `constraints[]` |
| `IssueCodeMapping` | `candidates[]{path, symbols[], score, confidence, labels[], evidence[]}`, `related_tests[]`, `dependencies[]`, `overall_confidence`, `model_version` |
| `ImpactAnalysis` | `changed_set[]`, `blast_radius{hop:int -> [symbol]}`, `callers[]`, `related_tests[]`, `public_api_touched[]`, `config_refs[]`, `db_refs[]`(INFERENCE), `regression_areas[]`, `risk_signal_bundle{}` |
| `EngineeringPlan` | `problem_interpretation`, `assumptions[]`, `files_to_inspect[]`, `files_to_modify[]`, `symbols_to_modify[]`, `dependencies[]`, `steps[]{id, description, test_intent, evidence_refs[]}`, `test_strategy{}`, `expected_behavior`, `regression_risks[]`, `rollback_strategy`, `source` |
| `PlanValidation` | `verdict` (`APPROVED`/`REVISE`/`REJECTED`), `reasons[]`, `checked{schema, files_exist, scope_subset, steps_have_tests, rollback_present, assumptions_nonempty}` |
| `ImplementationResult` | `edit_ops[]{path, op, anchor?, old?, new?, plan_step_id, rationale, evidence[]}`, `diff_ref`, `scope_violations[]` |
| `TestGeneration` | `tests[]{name, path, target_symbol?, kind, rationale, evidence[]}`, `targeted_selection[]` |
| `TestExecution` | `command`, `exit_code`, `results[]{test_id, outcome, duration_ms}`, `resource_usage{}`, `outcome`, `stdout_ref`, `stderr_ref` |
| `FailureAnalysis` | `failures[]{test_name, failure_type, frames[]}`, `facts[]`, `inferences[]`, `classification{}`, `evidence_bundle_ref` |
| `RootCauseAnalysis` | `hypotheses[]{statement, label, evidence[], rank}`, `most_likely_index`, `open_questions[]` |
| `RepairProposal` | `target_hypothesis`, `edit_ops[]`, `expected_effect`, `risk_notes[]` |
| `ReviewFinding` | `source`, `category`, `severity`, `file?`, `line_start?`, `line_end?`, `description`, `recommendation`, `confidence` |
| `PatchRiskAssessment` | `crs_value`, `crs_classification`, `crs_breakdown{signal -> contribution}`, `model_version` |
| `PatchConfidence` | `pcs_value`, `pcs_classification`, `pcs_breakdown{}`, `hard_gate?`, `model_version` |
| `VerificationResult` | `verdict`, `criteria[]{name, verdict, evidence[]}`, `plan_alignment{}`, `replay_fidelity?`, `trace_ref` |
| `PullRequestDraft` | `title`, `summary`, `issue_ref?`, `files_changed[]`, `tests_added[]`, `tests_executed[]`, `test_results{}`, `review_results{}`, `risk`, `confidence`, `known_limitations[]` |
| `EngineeringMemory` | `issue_text`, `touched_symbols[]`, `failure_signatures[]`, `fix_summary`, `plan_ref`, `patch_ref`, `review_summary{}`, `verification_verdict`, `outcome` |

Each schema also defines: required vs optional, enums, and **failure handling** — what the
consuming stage does when the field set indicates the agent could not proceed (always: record,
transition to `FAILED` or `PARTIALLY_SUPPORTED`, never fabricate).

---

## 8. Prompt-assembly rules

1. Templates live in `ai/prompts/` as named files; no inline prompt strings in agent code.
2. Instruction body is static; untrusted content goes only into `<data>`-style delimited blocks.
3. Every prompt states the exact JSON schema and says "if you cannot determine X, return
   `UNKNOWN` — do not guess".
4. Few-shot examples are schema-valid and checked in a unit test.
5. Context is assembled by a deterministic windowing function (priority: changed symbols > direct
   neighbours > related tests > history) that records what was dropped.

---

## 9. Open questions

| # | Question | Resolution |
|---|---|---|
| AA1 | embeddings for mapping + memory: hosted vs local | decide after the capability spike; optional with lexical+graph fallback |
| AA2 | should Verification ever use AI for the verdict itself | no — verdict is deterministic; AI only phrases the human-readable trace |
| AA3 | per-stage temperature | 0.0 everywhere for determinism/replay; revisit only if it hurts plan quality (measured Phase 25) |
