"""Deterministic failure-signature + fix-summary derivation for a memory record.

Pure functions -- the service passes already-loaded rows. The signature shape
matches ``app/debugging/guard.py::failure_signature`` (``"<outcome>|<sorted test
ids>"``) plus a per-frame ``"<failure_type>@<symbol_id>"`` form so retrieval can
match on "the same kind of failure in the same place".
"""

from __future__ import annotations


def failure_signatures(
    investigation,
    failures: list,
    repair_summary: dict | None,
) -> list[str]:
    sigs: list[str] = []

    if investigation is not None:
        cls = investigation.classification or {}
        test = cls.get("primary_test")
        sym = cls.get("primary_symbol_id")
        if test or sym:
            sigs.append(f"{test or '?'}@{sym or '?'}")

    for f in failures or []:
        ftype = getattr(f, "failure_type", None) or (
            f.get("failure_type") if isinstance(f, dict) else None
        )
        frames = getattr(f, "frames", None) or (
            f.get("frames") if isinstance(f, dict) else None
        )
        top_sym = None
        for fr in frames or []:
            sid = fr.get("symbol_id") if isinstance(fr, dict) else None
            if sid:
                top_sym = sid
                if fr.get("in_diff"):
                    break
        if ftype and top_sym:
            sig = f"{ftype}@{top_sym}"
            if sig not in sigs:
                sigs.append(sig)

    if repair_summary:
        safe_stop = repair_summary.get("safe_stop") or {}
        fs = safe_stop.get("failure_summary")
        if fs and fs not in sigs:
            sigs.append(str(fs))

    return sigs


def fix_summary(plan, verification, repair_summary: dict | None, outcome: str) -> str:
    parts: list[str] = []
    if plan is not None and getattr(plan, "problem_interpretation", None):
        parts.append(plan.problem_interpretation.strip())
    if outcome == "VERIFIED" and verification is not None:
        why = (verification.trace or {}).get("why_change")
        if why:
            parts.append(f"Change: {why}")
    if outcome == "SAFE_STOP" and repair_summary:
        safe_stop = repair_summary.get("safe_stop") or {}
        reason = safe_stop.get("reason") or repair_summary.get("outcome")
        action = safe_stop.get("recommended_human_action")
        if reason:
            parts.append(f"Safe-stopped: {reason}")
        if action:
            parts.append(f"Recommended: {action}")
    return " ".join(p for p in parts if p) or f"({outcome.lower()}, no summary)"
