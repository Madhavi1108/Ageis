# AEGIS Capability Spike (Stage A / Gate G0)

Traceability: `AEGIS_IMPLEMENTATION_PLAN.md` §7.1, §7.5 (G0); `ADR-0020`; `EVAL_HARNESS.md`.
Phase 0 deliverable (Spec §46 item 28, acceptance tests — the pre-build capability gate).

Status: **Harness built and passing on `MockProvider` + local fixtures (2026-09-04). Live run
against a real provider and the ~30-task benchmark subset is PENDING** — see §6.

---

## 1. Objective

Before building any product surface, prove the two capabilities the whole idea depends on:

1. **Issue -> code localization** — can AEGIS find the right file(s) given an issue description?
2. **End-to-end verified fix** — can a naive map -> plan -> patch -> run-tests loop actually fix a
   meaningful fraction of small, well-specified bugs?

If not, no amount of dashboard, Excel, or orchestration polish matters (`POSITIONING.md` §6).

---

## 2. Metrics and floors (`ADR-0020`)

| Metric | Formula | Floor |
|---|---|---|
| Localization recall@10 | `|top10_predicted ∩ gold_files| / |gold_files|`, averaged over tasks | `>= 0.75` |
| End-to-end verified-fix rate | `tasks_where_fail_to_pass_now_pass_and_pass_to_pass_still_pass / tasks_total` | `>= 0.30` |

---

## 3. Dataset

- **Target (live):** a ~30-task subset in the `EVAL_HARNESS.md` §2 task format (problem statement,
  repo@base_commit, gold_files, gold_patch, test_cmd, fail_to_pass, pass_to_pass), drawn from
  permissively licensed OSS issues with a clear reproducing test.
- **Wired now (mock proof):** `scripts/capability_spike/tasks.example.yaml` + `fixtures/` — three
  tiny, self-contained Python repos, each with one seeded bug, a gold file list, and a test that
  passes iff the bug is fixed. These prove the harness end-to-end; they are **not** a substitute
  for the live 30-task run (too small, too easy, hand-authored).

---

## 4. Harness design

`scripts/capability_spike/run.py` drives, per task:

```
1. load the fixture/task repo at base_commit into a scratch dir
2. mapping.py: lexical (inverted index over files+docstrings) + import-graph proximity
              -> ranked file list with evidence           [feeds recall@10]
3. provider.py: one planning call (MockProvider or a real provider) -> a small structured
                edit-op list against the top-ranked file(s)
4. apply the edit ops (anchored, minimal) to a working copy
5. run test_cmd (local subprocess for the spike -- NOT the hardened Docker sandbox;
   the spike is throwaway wiring, not a security boundary)
6. metrics.py: check fail_to_pass now pass and pass_to_pass still pass -> verified_fix (bool)
7. record per-task: predicted_files, gold_files, recall@10 contribution, verified_fix
```

Aggregate: mean recall@10, and `verified_fix_rate = mean(verified_fix)`.

**This harness is explicitly throwaway** (`scripts/capability_spike/README.md`): it reuses no
`backend/` code, is not security-hardened, and exists only to (a) prove the mapping+loop design
before investing in the real Phases 2–18, and (b) generate the mock-run numbers below.

---

## 5. Results

### 5.1 Mock run (wiring proof — labelled MOCK, not a capability measurement)

Run: `python scripts/capability_spike/run.py --provider mock --tasks
scripts/capability_spike/tasks.example.yaml`

| Run | Tasks | Localization recall@10 | Verified-fix rate | Notes |
|---|---|---|---|---|
| MOCK (2026-09-04) | 3 (`tasks.example.yaml`) | 1.00 | 1.00 | `MockProvider` returns a canned, correct edit-op for each fixture task by design — this proves the **pipeline wiring and metric computation are correct**, not that AEGIS can localize/fix real issues. Numbers are necessarily high/trivial and must not be read as a capability result. |

Reproduce with `python scripts/capability_spike/run.py --provider mock --tasks
scripts/capability_spike/tasks.example.yaml` — confirmed deterministic (two consecutive runs
produced byte-identical output on 2026-09-04).

### 5.2 Live run — **PENDING LIVE RUN**

| Run | Tasks | Localization recall@10 | Verified-fix rate | Decision |
|---|---|---|---|---|
| LIVE | ~30-task benchmark subset | **PENDING** | **PENDING** | **PENDING** |

**Required to execute:**

1. A real `AIProvider` credential (e.g. `ANTHROPIC_API_KEY` for `ClaudeProvider`, or
   `OPENAI_API_KEY` for `OpenAIProvider`).
2. The assembled ~30-task benchmark subset (`EVAL_HARNESS.md` §1–§2) — not yet collected.
3. Docker, if the live run is upgraded from the spike's plain-subprocess execution to the hardened
   sandbox before measuring (recommended once real, less-trusted repos are involved).

**Exact command once inputs exist:**

```
AEGIS_SPIKE_PROVIDER=claude ANTHROPIC_API_KEY=*** \
  python scripts/capability_spike/run.py --provider claude --tasks <path-to-30-task-set.yaml>
```

---

## 6. Decision framework (gate G0)

| Outcome | Action |
|---|---|
| Both floors met | Proceed to Phase 1 (walking skeleton) with the mapping/planning design as spiked. |
| One or both floors missed | Up to **two bounded redesign rounds** (retrieval weighting/chunking, prompt/planning changes), re-run, re-measure. |
| Still below after two rounds | Invoke the re-scope path in `POSITIONING.md` §6: assisted mode (human-in-the-loop suggestions) or a narrower task class (dependency bumps, lint/typing fixes, small well-specified bugs) where the floor is reachable. |

**Current status: not yet evaluable — live numbers are pending (§5.2).** The mock run confirms the
harness itself is correct and ready to receive live inputs. Phase 1 may proceed on schedule per
the plan, but G0 must be revisited with live numbers before Phase 2's breadth work accelerates, and
before any external claim of capability is made.
