# AEGIS Positioning

Traceability: `AEGIS_IMPLEMENTATION_PLAN.md` §2.1–§2.4 (strategic thesis, wedge, non-goals,
competitive baseline). Phase 0 deliverable (plan addition). `ADR-0020` records the capability
gates that keep this positioning falsifiable.

Status: Accepted — 2026-09-04.

---

## 1. Strategic thesis

Raw model capability is a rapidly commoditizing input shared with every competitor. AEGIS competes
on **trust per change**: a team hands AEGIS a task and receives not just a diff but a verifiable,
auditable, reproducible engineering record proving the change is correct, in-scope, and safe.

Three durable assets:

1. **Verifiable autonomy** — every change ships with an evidence trace, deterministic risk +
   confidence scores, an executed test record, and a verification verdict a human can audit in
   minutes instead of re-reviewing from scratch.
2. **Repository memory moat** — a persistent per-repository knowledge graph + engineering memory
   that compounds: the hundredth task on a codebase is cheaper, faster, and more accurate than the
   first. A competitor starting cold on that codebase cannot match it.
3. **Deterministic replay** — given the same inputs and recorded model/seed metadata, a task
   re-runs to the same patch. This is what makes AEGIS acceptable where opaque AI commits are a
   non-starter.

---

## 2. The wedge

- **Primary user:** engineering teams on large, long-lived **Python** codebases who currently
  cannot accept autonomous changes because they cannot audit them — regulated industries,
  security-sensitive products, platform/infra teams, enterprises with heavy change control.
- **Primary buyer:** an engineering leader accountable for change safety and review throughput.
- **Primary job:** convert a well-specified issue into a **review-ready, evidence-backed** change,
  cutting human review time and closing the "AI wrote this — now what?" gap.
- **Beachhead:** the controlled-repository workflow (Phase 24) generalized to a customer's own
  service repos, sold on review-time reduction and audit completeness — not on autonomy theater.

---

## 3. Non-goals

- Not a general IDE assistant, chat companion, or autocomplete. AEGIS is task-in / verified-change-
  out (Spec §52).
- Not chasing raw public-benchmark SOTA. AEGIS optimizes verified-change quality, false-complete
  rate, cost per verified task, and auditability — even when that shows a lower headline
  resolution rate than marketing-driven competitors.
- Not multi-language at MVP. Python-first; the abstraction seams exist but everything else is
  `UNSUPPORTED` until implemented and tested.
- Not a replacement for human judgment on high-risk changes — those route to `AWAITING_APPROVAL`
  by policy.

---

## 4. Competitive landscape

Snapshot as of 2026-09; treat as directional, not a scorecard. Names are grouped by what they
optimize for.

| Product / project | Shape | What AEGIS does differently |
|---|---|---|
| Devin (Cognition) | hosted autonomous SWE agent | AEGIS exposes every stage as an inspectable typed artifact + deterministic scores + replay; audit-first rather than demo-first |
| GitHub Copilot coding agent | issue -> PR inside GitHub | AEGIS is repo-host-agnostic, runs an explicit verification gate with a false-complete ceiling, and produces a Trust Report; PR creation is one optional output, not the product |
| Cursor / Windsurf agents | IDE-embedded agents | AEGIS is a pipeline service, not an editor; optimized for unattended, reviewable batch tasks |
| OpenHands (open source) | agent framework + runtime | AEGIS is a fixed 7-agent typed pipeline, not a general framework; used as a **reference baseline** for metric #15 |
| SWE-agent (open source) | benchmark-oriented agent | used as a **reference baseline**; AEGIS reports verified-quality delta vs it on identical tasks |
| Aider (open source) | pair-programming CLI | interactive; AEGIS is autonomous + verified; also a reference baseline |
| Google Jules | async coding agent | similar async shape; AEGIS differentiates on audit trail, deterministic replay, and the repository-memory moat |
| Amazon Q Developer | AWS-centric assistant + agents | AEGIS is cloud-neutral and self-hostable (LocalProvider path) for teams that cannot send code to a third party |

---

## 5. Why this can win

- The buyers who most need autonomy (regulated / large-legacy / security-sensitive) are the ones
  least served by opaque agents. Auditability is a real, unmet requirement, not a nice-to-have.
- The repository-memory moat compounds with usage and is per-customer — it is not something a
  competitor can pre-build.
- Deterministic replay + the tamper-evident audit chain are concrete artifacts a compliance
  function can point at.

## 6. What would make us stop (kill / pivot)

Evaluated at the decision gates in plan §7.5 / `ADR-0020`:

- **G0 (capability spike):** if issue->code localization `recall@10 < 0.75` or end-to-end
  verified-fix rate `< 0.30` on the 30-task subset and two bounded redesign rounds do not recover
  it -> re-scope to **assisted** mode (human-in-loop suggestions) or a **narrower task class**
  (dependency bumps, lint/typing fixes, small well-specified bugs) where the floor is reachable.
- **G2 (verification):** if the false-complete rate cannot be held at or below 2%, do not ship
  autonomy — the wedge is trust, and a system that says "done" when it is not destroys it.
- **G3 (release):** if the competitive verified-quality delta is negative and cannot be recovered,
  or the cost per verified task is outside the `COST_MODEL.md` envelope, hold release and fix the
  failing dimension.
