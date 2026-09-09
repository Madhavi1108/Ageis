# AEGIS Final Acceptance Contract

The 30 final acceptance criteria (Specification §54) and the 20 absolute rules
(Specification §55), each mapped to the code that satisfies it and a test that
demonstrates it. `backend/tests/docs/test_acceptance_contract.py` checks that
every evidence path below exists.

Status: final — reconciled against the built system (Phases 0–28), 2026-09-09.

Evidence conventions: paths are repo-relative. The end-to-end demonstration for
almost every criterion is
`backend/tests/e2e/test_full_pipeline.py::test_scenario_a_drives_all_18_workflow_steps`,
which drives the acceptance repository through all 18 workflow steps and asserts
each one; the per-stage `*_acceptance_fixture.py` integration tests demonstrate
the stage in isolation against the same fixture.

---

## Part 1 — Final acceptance criteria (§54)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | A real repository can be ingested | MET | `backend/tests/integration/test_ingest_local_fixture.py`; `backend/tests/integration/test_ingest_git_fixture.py` |
| 2 | Repository structure can be analyzed | MET | `backend/tests/integration/test_analyze_acceptance_fixture.py` |
| 3 | Symbols and dependencies can be identified | MET | `backend/tests/integration/test_analyze_acceptance_fixture.py`; `backend/tests/integration/test_analyze_builds_graph.py` |
| 4 | Git history can be analyzed | MET | `backend/tests/integration/test_git_api.py` |
| 5 | A real issue can be submitted | MET | `backend/tests/integration/test_task_acceptance_fixture.py` |
| 6 | Relevant code can be identified | MET | `backend/tests/integration/test_mapping_acceptance_fixture.py` |
| 7 | Evidence-backed impact analysis can be generated | MET | `backend/tests/integration/test_impact_acceptance_fixture.py` |
| 8 | A structured engineering plan can be created | MET | `backend/tests/integration/test_planning_api.py`; `backend/tests/integration/test_planning_no_provider.py` |
| 9 | The plan can be validated | MET | `backend/tests/integration/test_planning_api.py` |
| 10 | Real code can be modified | MET | `backend/tests/integration/test_implementation_acceptance_fixture.py` |
| 11 | Tests can be generated | MET | `backend/tests/integration/test_testing_acceptance_fixture.py` |
| 12 | Tests can execute in a sandbox | MET (fake); PARTIALLY_SUPPORTED (Docker) | `backend/tests/integration/test_execution_acceptance_fixture.py`; `backend/tests/e2e/test_full_pipeline.py::test_docker_variant_reaches_verified` (skipped without a daemon) |
| 13 | Failures can be detected | MET | `backend/tests/integration/test_execution_acceptance_fixture.py`; `backend/tests/integration/test_investigation_acceptance_fixture.py` |
| 14 | Root causes can be investigated | MET | `backend/tests/integration/test_investigation_acceptance_fixture.py` |
| 15 | Repair attempts can be performed | MET | `backend/tests/integration/test_repair_acceptance_fixture.py` |
| 16 | Regression tests can execute | MET | `backend/tests/integration/test_regression_acceptance_fixture.py` |
| 17 | Generated changes can be reviewed | MET | `backend/tests/integration/test_review_acceptance_fixture.py` |
| 18 | Scope violations can be detected | MET | `backend/tests/integration/test_implementation_acceptance_fixture.py`; `backend/tests/integration/test_review_acceptance_fixture.py` |
| 19 | Risk can be calculated | MET | `backend/tests/integration/test_scoring_acceptance_fixture.py`; `backend/tests/unit/test_scoring_risk.py` |
| 20 | Confidence can be calculated | MET | `backend/tests/integration/test_scoring_acceptance_fixture.py`; `backend/tests/unit/test_scoring_confidence.py` |
| 21 | Final verification can be performed | MET | `backend/tests/integration/test_verification_acceptance_fixture.py` |
| 22 | A real patch / diff can be produced | MET | `backend/tests/integration/test_implementation_acceptance_fixture.py` |
| 23 | Git branch / commit can be created | MET | `backend/tests/integration/test_pr_acceptance_fixture.py`; `backend/tests/integration/test_git_api.py` |
| 24 | GitHub PR can be created when credentials permit | PARTIALLY_SUPPORTED | `backend/tests/integration/test_pr_acceptance_fixture.py`; `backend/tests/integration/test_pr_api.py` — local PR artifact always; a real PR only on a GitHub 201 + stored URL (Rule 8) |
| 25 | Engineering memory can persist the task | MET | `backend/tests/integration/test_memory_acceptance_fixture.py` |
| 26 | Dashboard can show the actual workflow | MET | `frontend/src/test/integration/taskFlow.test.tsx`; `frontend/src/test/integration/everyPanelCallsBackend.test.tsx` |
| 27 | FastAPI exposes the workflow | MET | `backend/tests/integration/test_openapi_snapshot.py`; `backend/tests/integration/test_tasks_api.py` |
| 28 | Excel reports use real backend data | MET | `backend/tests/integration/test_reporting_acceptance_fixture.py`; `backend/tests/integration/test_reports_api.py` |
| 29 | Failures are handled safely | MET | `backend/tests/e2e/test_full_pipeline.py::test_scenario_c_unfixable_reaches_safe_stop`; `backend/tests/integration/test_repair_acceptance_fixture.py`; `backend/tests/security/` |
| 30 | No fake functionality is used | MET | `backend/tests/unit/test_acceptance_fixture_integrity.py`; `frontend/src/test/integration/everyPanelCallsBackend.test.tsx`; the full suite (`backend/tests/e2e/test_full_pipeline.py`) |

**End-to-end sign-off:** `backend/tests/e2e/test_full_pipeline.py` — scenario A
reaches `COMPLETED` through all 18 steps, scenario B creates new files, scenario
C reaches a clean `SAFE_STOP`. Re-run as `python scripts/quickstart_check.py`.

---

## Part 2 — Absolute rules audit (§55)

| Rule | Where enforced | Evidence |
|---|---|---|
| 1 No disconnected modules | orchestrator connectedness invariant (each stage's input = prior stage's output) | `backend/tests/integration/test_orchestrator_pipeline.py` |
| 2 Don't optimize for agent count | 7 fixed agents (ADR-0004) | `docs/DECISIONS/ADR-0004-agent-orchestration.md` |
| 3 AI code is not automatically correct | execute + review + verify before any success claim | `backend/tests/e2e/test_full_pipeline.py::test_scenario_a_drives_all_18_workflow_steps` |
| 4 Every implementation executed and tested | execution stage gates completion | `backend/tests/integration/test_execution_acceptance_fixture.py` |
| 5 Every AI conclusion has evidence | `evidence` field on every AI schema; validated | `backend/tests/integration/test_mapping_acceptance_fixture.py`; `backend/tests/integration/test_planning_api.py` |
| 6 Every score has an explicit algorithm | `scoring-model v1.0.0` constants; code↔doc sync | `backend/tests/unit/test_scoring_model_version_sync.py` |
| 7 Never claim a test passed unless it executed and passed | `TestExecution` outcome tracking; `INVALID` vs executed | `backend/tests/integration/test_execution_acceptance_fixture.py`; `backend/tests/integration/test_verification_acceptance_fixture.py` |
| 8 Never claim a PR exists unless created | PR row only on API 201 + stored URL | `backend/tests/integration/test_pr_acceptance_fixture.py` |
| 9 Never execute untrusted code on the host | Docker sandbox; host-subprocess spy tests | `backend/tests/integration/test_ingest_no_untrusted_execution.py`; `backend/tests/security/test_subprocess_guard.py` |
| 10 Never expose credentials | log redaction + secret scanner (CI gate) | `backend/tests/security/test_secret_scan.py` |
| 11 Every repair loop bounded | iterations + wall-clock + no-progress stop | `backend/tests/integration/test_repair_acceptance_fixture.py`; `backend/tests/e2e/test_full_pipeline.py::test_scenario_c_unfixable_reaches_safe_stop` |
| 12 Every patch reversible | baseline commit + rollback | `backend/tests/integration/test_implementation_acceptance_fixture.py` |
| 13 Scope expansion detected | scope tracker; review + verification | `backend/tests/integration/test_implementation_acceptance_fixture.py`; `backend/tests/integration/test_review_acceptance_fixture.py` |
| 14 Execution results outrank AI | precedence in investigate/repair/verify | `backend/tests/integration/test_verification_acceptance_fixture.py` |
| 15 Don't hide uncertainty | `UNKNOWN` / confidence fields; low-confidence fallback | `backend/tests/integration/test_planning_no_provider.py`; `backend/tests/unit/test_ai_context.py` |
| 16 Don't fabricate metrics | metrics generated by the harness, not hard-coded; docs scan | `backend/tests/integration/test_benchmark_pipeline.py`; `backend/tests/unit/test_benchmark_calibrate.py` |
| 17 No critical features as TODOs | Definition of Done; every phase ends verified | `backend/tests/e2e/test_full_pipeline.py` |
| 18 Don't stop at architecture / scaffolding | every phase ends in working functionality | `backend/tests/e2e/test_full_pipeline.py` |
| 19 Not a presentation prototype | every dashboard panel calls the backend | `frontend/src/test/integration/everyPanelCallsBackend.test.tsx` |
| 20 Optimize for working integrated functionality | milestone exit gates; full e2e | `backend/tests/e2e/test_full_pipeline.py` |

---

## Open items (disclosed, not blocking the contract)

- The Docker sandbox **happy path** has not run against a live daemon in this
  environment; `PARTIALLY_SUPPORTED` degradation is verified, container
  hardening rests on the sandbox-policy unit tests.
- The Phase 0 capability spike (G0) and this contract have not been re-run
  against a **live AI provider** on a real benchmark subset.
- Metric #15 (competitive resolution-rate delta) needs real reference agents —
  currently N/A.
- The worker is single sequential; `limit_graph_nodes` is config-only.
