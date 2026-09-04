# Task: Fix incorrect invoice total when discount exceeds the configured maximum

Applying a discount above 50% still charges the full requested discount instead of capping it.

Fix `calculate_total()` in the invoice module so that any discount above 0.5 (50%) is capped at
0.5 before being applied to the price. Add a test that verifies the boundary condition (a
90% discount should behave the same as a 50% discount).

This is the AEGIS acceptance-repository seed task (Specification Section 39's worked example),
used to drive the Phase 1 Walking Skeleton end-to-end: REQUIREMENT -> VERIFIED DIFF.
