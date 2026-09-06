"""``scoring-model v1.0.0`` -- the versioned parameter registry for the Patch
Confidence Score, Change Risk Score, and Repository Health Profile.

The constants below are this module's *copy* of the single source of truth:
**docs/METRICS.md Section 2**. ``tests/unit/test_scoring_model_version_sync.py``
asserts the two stay equal, and any change here must bump
``SCORING_MODEL_VERSION`` **and** edit ``docs/METRICS.md`` in the same commit
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 8 regression gate:
"a CI job fails if a later phase changes a scoring constant ... without bumping
the relevant *_version"; ADR-0017).

Every value is ``v1.0.0`` **provisional** -- calibrated against a labelled
dataset in Phase 25 (docs/METRICS.md Section 5). Each carries a one-line
rationale so no number is arbitrary (Specification Section 13 / Absolute Rule
"every score has an explicit algorithm").
"""

from __future__ import annotations

SCORING_MODEL_VERSION = "scoring-model v1.0.0"

# --------------------------------------------------------------------------- #
# 1. Patch Confidence Score (PCS), 0-100, higher = safer to accept
#    docs/METRICS.md Section 2.1
# --------------------------------------------------------------------------- #

#: signal name -> weight. Mirrors docs/METRICS.md Section 2.1. Sums to 1.0.
PCS_WEIGHTS: dict[str, float] = {
    "targeted_pass": 0.22,     # direct evidence the change does what was asked
    "regression_pass": 0.22,   # direct evidence nothing else broke
    "review_clean": 0.15,      # reviewer signal; criticals dominate
    "coverage": 0.10,          # untested change lines are unverified
    "scope_clean": 0.10,       # out-of-scope edits erode trust
    "size_fit": 0.06,          # large diffs are harder to be confident in
    "dep_fit": 0.05,           # more callers = more ways to be wrong; floored
    "history_stable": 0.04,    # churny files are historically fragile
    "repair_fit": 0.04,        # many repair rounds signal a shaky fix
    "ai_selfconf": 0.02,       # weak signal; small, capped weight
}

# review_clean = 1 - min(1, (RC_CRITICAL*critical + RC_HIGH*high + RC_MEDIUM*medium) / RC_DIVISOR)
PCS_REVIEW_CLEAN_CRITICAL_COEFF = 2.0   # a CRITICAL counts double toward "unclean"
PCS_REVIEW_CLEAN_HIGH_COEFF = 1.0       # a HIGH counts once
PCS_REVIEW_CLEAN_MEDIUM_COEFF = 0.4     # a MEDIUM is a fractional concern
PCS_REVIEW_CLEAN_DIVISOR = 5.0          # ~5 weighted findings saturates the signal

PCS_SIZE_FIT_DIVISOR = 400.0    # size_fit = clamp(1 - lines_changed / 400, 0, 1); ~400 LOC = no confidence from size
PCS_DEP_FIT_DIVISOR = 25.0      # dep_fit = clamp(1 - impacted_callers / 25, FLOOR, 1)
PCS_DEP_FIT_FLOOR = 0.2         # never let caller count alone zero out the score
PCS_AI_SELFCONF_CAP = 0.8      # provider-reported confidence contributes at most this (before its 0.02 weight)

#: PCS >= value -> classification. Below the lowest is VERY_LOW. docs/METRICS.md Section 2.1.
PCS_CLASSIFICATION: dict[str, int] = {"HIGH": 85, "MEDIUM": 70, "LOW": 50}

#: security_gate multiplier applied to PCS_raw. docs/METRICS.md Section 2.1.
PCS_SECURITY_GATE: dict[str, float] = {
    "clean": 1.0,            # no security finding >= HIGH
    "medium_open": 0.6,      # an open MEDIUM security finding
    "high_unresolved": 0.0,  # an unresolved HIGH/CRITICAL security finding
}

#: hard override: an unresolved CRITICAL review finding, an unresolved scope
#: violation, or any failing regression test caps PCS here and forces BLOCKED.
PCS_HARD_CAP = 40

# --------------------------------------------------------------------------- #
# 2. Change Risk Score (CRS), 0-100, higher = riskier
#    docs/METRICS.md Section 2.2
# --------------------------------------------------------------------------- #

#: signal name -> weight. Mirrors docs/METRICS.md Section 2.2. Sums to 1.0.
CRS_WEIGHTS: dict[str, float] = {
    "files_changed": 0.10,             # breadth of change
    "lines_changed": 0.10,            # size of change
    "dependency_impact": 0.12,        # how much downstream code is exposed
    "public_api_touched": 0.15,       # external contract risk is high-weight
    "inverse_coverage": 0.13,         # untested change lines are the main risk
    "historical_churn": 0.08,         # fragile areas
    "prior_failures": 0.10,           # repeat-offender areas
    "architectural_centrality": 0.12,  # central code breaks more things
    "complexity_delta": 0.05,         # added branching
    "security_sensitivity": 0.05,     # sensitive surface
}

CRS_FILES_DIVISOR = 10.0        # files_changed norm = clamp(n / 10, 0, 1)
CRS_LINES_DIVISOR = 300.0       # lines_changed norm = clamp(loc / 300, 0, 1)
CRS_DEP_DIVISOR = 30.0          # dependency_impact norm = clamp(impacted_symbols / 30, 0, 1)
CRS_PRIOR_FAILURES_DIVISOR = 3.0   # prior_failures norm = clamp(failures_in_area / 3, 0, 1)
CRS_COMPLEXITY_DIVISOR = 20.0   # complexity_delta norm = clamp(added_cyclomatic / 20, 0, 1)

#: CRS <= value -> classification band. Above the highest is CRITICAL.
#: Bands: 0-24 LOW, 25-49 MEDIUM, 50-74 HIGH, 75-100 CRITICAL. docs/METRICS.md Section 2.2.
CRS_CLASSIFICATION: dict[str, int] = {"LOW": 24, "MEDIUM": 49, "HIGH": 74}

# --------------------------------------------------------------------------- #
# 3. Repository Health Profile (RHP), 0-100, higher = healthier
#    docs/METRICS.md Section 2.3
# --------------------------------------------------------------------------- #

#: sub-score name -> weight. Mirrors docs/METRICS.md Section 2.3. Sums to 1.0.
RHP_WEIGHTS: dict[str, float] = {
    "maintainability": 0.25,               # maintainability index
    "test_coverage": 0.25,                # test coverage
    "inverse_dependency_coupling": 0.15,  # inverse dependency coupling
    "churn_stability": 0.15,              # churn stability
    "documentation_ratio": 0.10,          # documentation ratio
    "ci_presence": 0.10,                  # CI presence
}

#: RHP >= value -> classification. Below the lowest is VERY_LOW. Same bands as PCS.
RHP_CLASSIFICATION: dict[str, int] = {"HIGH": 85, "MEDIUM": 70, "LOW": 50}

#: risky_modules = files in the top (1 - decile) fraction by
#: centrality * churn * inverse_coverage * complexity. docs/METRICS.md Section 2.3.
RHP_RISKY_MODULES_DECILE = 0.9

RHP_COUPLING_DIVISOR = 8.0    # inverse_dependency_coupling = 1 - clamp(mean_fan_in_out / 8, 0, 1); ~8 edges/node = maximal coupling
RHP_MAINTAINABILITY_LOC_DIVISOR = 60.0   # maintainability proxy = 1 - clamp(mean symbol span LOC / 60, 0, 1); coarse v1.0.0 proxy pending radon (Phase 25)

# --------------------------------------------------------------------------- #
# 4. Unavailable-signal handling (docs/METRICS.md Section 2.5)
# --------------------------------------------------------------------------- #

#: a "higher = better" signal (PCS signals, RHP sub-scores) with no data source
#: contributes this neutral prior -- not 1.0 (would flatter a patch) and not 0.0
#: (would punish it for missing instrumentation).
UNAVAILABLE_PRIOR_GOOD = 0.5

#: a "higher = riskier" signal (CRS signals) with no data source contributes
#: 0.0 -- absence of evidence is never invented as risk.
UNAVAILABLE_PRIOR_RISK = 0.0

# --------------------------------------------------------------------------- #

_SUMS = {
    "PCS_WEIGHTS": sum(PCS_WEIGHTS.values()),
    "CRS_WEIGHTS": sum(CRS_WEIGHTS.values()),
    "RHP_WEIGHTS": sum(RHP_WEIGHTS.values()),
}
for _name, _total in _SUMS.items():
    if round(_total, 9) != 1.0:  # pragma: no cover - guards a typo in this file
        raise ValueError(f"{_name} must sum to 1.0, got {_total}")
