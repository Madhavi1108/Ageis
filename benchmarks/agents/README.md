# Reference agents (metric #15)

Metric #15 — **Competitive Resolution-Rate Delta** — is

    aegis_verified_scope_clean_rate  −  best_reference_agent_rate

computed on the **identical** task set, with the same `fail_to_pass` / `pass_to_pass`
criterion (`docs/EVAL_HARNESS.md` §4).

## Status

Only `NoopReferenceAgent` ships wired. In this environment there is no Docker, no
network, and no model credential, so no real agent runs and the report shows
`#15  N/A — no reference agents configured`.

## Wiring a real agent

Implement `benchmarks.agents.base.ReferenceAgent`:

```python
class AiderAgent:
    name = "aider"
    is_baseline = True

    def solve(self, task, workdir):
        # run aider in batch mode against `workdir` with task.problem_statement,
        # in its own container, same CPU/mem/wall-clock limits as the AEGIS sandbox.
        # return True if it changed files.
        ...
```

Then pass instances to `benchmarks.runner.run_dataset(..., reference_agents=[AiderAgent(), ...])`
(or `python -m benchmarks run --dataset <name> --reference aider,openhands` once an
entry-point registry is added). Pin each agent's version per run and record it in
`docs/BENCHMARK_RESULTS.md` (EH3). Candidates: **OpenHands** or **SWE-agent** (one
general autonomous agent) + **Aider** (lighter, batch mode).

Only agents with `is_baseline = True` contribute to the #15 delta.
