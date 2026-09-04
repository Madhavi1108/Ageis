# Task: round_half_up() does not round halves up

`round_half_up(2.5)` returns 2, not 3. Fix the rounding function so that .5 values always round
up, matching its name and docstring.

This fixture deliberately has no canned MockProvider response (see
`aegis/ai/provider.py::MockProvider`), so the walking skeleton falls back to its generic
low-confidence plan, which does not fix the bug. It exists to test that the bounded repair loop
exhausts its two attempts and the pipeline ends cleanly at `NOT_VERIFIED` with a populated
`TrustReportV0.limitations` -- not a crash, not a false `VERIFIED`.
