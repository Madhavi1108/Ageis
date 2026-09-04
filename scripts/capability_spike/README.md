# AEGIS Capability Spike Harness

**This is throwaway wiring, not part of `backend/` and not the hardened AEGIS pipeline.** It
exists solely to satisfy the Stage A capability spike in `docs/CAPABILITY_SPIKE.md` (gate G0,
`AEGIS_IMPLEMENTATION_PLAN.md` §7.1). It has no Docker sandbox, no persistence, no orchestrator,
and is not security-hardened — do not point it at an untrusted repository.

## What it does

For each task in a YAML file:

1. Copies the task's tiny fixture repo into a scratch directory.
2. Ranks candidate source files against the issue text (`mapping.py`: lexical + symbol-name
   overlap) → measures **localization recall@10**.
3. Asks a provider (`provider.py`) for a structured edit-op.
4. Applies the edit-op to the scratch copy.
5. Runs the task's `fail_to_pass` and `pass_to_pass` test ids with `pytest` → measures
   **verified-fix rate**.
6. Prints per-task results and the aggregate numbers.

## Run it — mock (no API key, deterministic, CI-safe)

```
python scripts/capability_spike/run.py --provider mock --tasks scripts/capability_spike/tasks.example.yaml
```

This uses `MockProvider`, which returns each task's own canned `mock_fix` — it proves the harness
and the metric computation are correct, **not** that AEGIS can localize or fix real issues. See
`docs/CAPABILITY_SPIKE.md` §5.1.

## Run it — live (requires a real provider + the real benchmark subset)

```
AEGIS_SPIKE_PROVIDER=claude ANTHROPIC_API_KEY=*** \
  python scripts/capability_spike/run.py --provider claude --tasks <path-to-30-task-benchmark-subset.yaml>
```

Requires: an API key for the chosen provider, and the ~30-task benchmark subset described in
`docs/EVAL_HARNESS.md` (not included here — `tasks.example.yaml` is 3 hand-authored wiring-proof
fixtures, far too small and too easy to stand in for the real spike). This live run is what
`docs/CAPABILITY_SPIKE.md` §5.2 currently marks **PENDING**.

## Files

| File | Purpose |
|---|---|
| `run.py` | driver: load tasks, map, plan, patch, test, report |
| `mapping.py` | lexical + symbol-name file ranking (precursor to `docs/REPOSITORY_ANALYSIS.md` §5) |
| `provider.py` | `MockProvider` (deterministic) + `ClaudeProvider`/`OpenAIProvider` shims for the live run |
| `metrics.py` | `recall@k` and verified-fix-rate computation (mirrors `docs/METRICS.md` #1) |
| `tasks.example.yaml` | 3 wiring-proof tasks referencing `fixtures/` |
| `fixtures/*/` | tiny self-contained Python "repos", each with one seeded bug + distractor files + tests |

## Mapping to `docs/CAPABILITY_SPIKE.md`

This harness implements the design in `docs/CAPABILITY_SPIKE.md` §4. Results go in that
document's §5; the go / redesign / re-scope decision in its §6 is made from the **live** numbers,
never the mock ones.
