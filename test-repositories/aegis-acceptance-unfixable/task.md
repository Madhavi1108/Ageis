# Task: round_half_away() does not round halves away from zero

`round_half_away(2.5)` returns 2, not 3, because it delegates to Python's built-in `round()`
(banker's rounding). Fix `round_half_away()` in `rounding.py` so that half values always round
away from zero, matching its name and docstring.

This is the AEGIS acceptance-repository **unfixable** scenario (scenario C). The seeded
MockProvider answers for this task deliberately contain no correct fix -- the canned
implementation and repair proposals are ineffective on purpose -- so the bounded 2..N-attempt
repair loop exhausts without going green and the pipeline ends cleanly at `SAFE_STOP` with a
populated `SafeStop` payload. It exists to prove the negative path is safe: no crash, no false
`VERIFIED`. See `docs/ACCEPTANCE_SCENARIOS.md`.
