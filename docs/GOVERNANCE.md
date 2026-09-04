# AEGIS Governance, Audit & Deterministic Replay

Traceability: `AEGIS_IMPLEMENTATION_PLAN.md` §4.14; Specification §24, §25, §29, §34; metric #16.
Phase 0 deliverable (plan addition). `ADR-0011` (security policy), `ADR-0016` (memory).

Status: Accepted — 2026-09-04.

---

## 1. Purpose

Make an AEGIS change acceptable where an opaque AI commit is not. Four mechanisms: deterministic
replay, a tamper-evident audit chain, RBAC, and explicit data-handling guarantees — surfaced
together in a per-change **Trust Report**.

---

## 2. Deterministic replay (metric #16)

Every task records, in a `ReplayManifest` artifact:

- task input (repository ref + commit, sanitized issue/task fields, constraints, allowed paths);
- resolved provider + model id per stage, request params (`temperature=0.0`, `top_p`, max tokens),
  and any seed the provider exposes;
- `mapping-model` / `scoring-model` / `pricing-table` versions;
- the deterministic context-windowing decisions (what was included/dropped per stage);
- tool versions (Python, `ast`, sandbox image digest).

**Replay** re-runs the task from the manifest and asserts the produced `Patch` (and the key
intermediate artifacts: `IssueCodeMapping`, `EngineeringPlan`, diff) are byte-identical.

Non-determinism that cannot be eliminated (a provider without seed support) is **disclosed** in the
Trust Report as `replay_fidelity < 1.0` with the reason — never hidden. Metric #16 aggregates
replay fidelity across a benchmark sample; gate G3 requires `>= 0.9`.

Determinism aids already in the design: `temperature=0.0`, stable ordering everywhere, no
wall-clock in artifacts, `PYTHONHASHSEED=0` in subprocesses, `MockProvider` for all non-live tests.

---

## 3. Tamper-evident audit chain

`AuditLog` rows form a hash chain (see `DATA_MODEL.md` §2.5):

```
entry_hash = sha256(seq || prev_hash || actor || action || target_type || target_id
                    || payload_digest || created_at_iso)
payload_digest = sha256(canonical_json(redacted_payload))
```

- One row per **mutating** API call and per **autonomous** action: repo ingested, plan approved,
  patch applied, test executed, repair attempt, review completed, scope override, risk override,
  PR created, approval granted/denied, config changed.
- `actor` is a subject id, or `SYSTEM`, or `AGENT:<name>`.
- Append-only: no `UPDATE`, no `DELETE` at the ORM layer; on PostgreSQL, enforced with a table
  privilege (`REVOKE UPDATE, DELETE`).
- `GET /audit/verify` walks the chain and returns `{ok: bool, first_break_seq?: int}`.
- `GET /audit?task_id=...` returns the task's slice for the dashboard timeline.
- Redaction: payloads are digested after the secret-redaction filter; raw prompts / tokens never
  enter a payload.

---

## 4. RBAC

| Role | Grants (cumulative) |
|---|---|
| `viewer` | read tasks, timelines, plans, diffs, reviews, verifications, reports, audit slices |
| `operator` | + create / run / cancel tasks; ingest repositories; request re-analysis |
| `approver` | + resolve `AWAITING_APPROVAL`; override a scope violation or a risk gate (reason required, audit-logged) |
| `admin` | + manage providers, policy, limits, users, retention |

Route -> minimum role (representative):

| Route | Min role |
|---|---|
| `GET /tasks/**`, `GET /repositories/**`, `GET /reports/**`, `GET /audit/**` | viewer |
| `POST /repositories`, `POST /tasks`, `POST /tasks/{id}/run`, `POST /tasks/{id}/cancel` | operator |
| `POST /tasks/{id}/approve`, `POST /tasks/{id}/override` | approver |
| `POST /tasks/{id}/pr` (GitHub write) | approver |
| `PUT /config/**`, `POST /providers/**`, `PUT /policy/**` | admin |

Auth is an API key or JWT in the MVP; every mutating route declares its required role in code and
in OpenAPI.

---

## 5. Data-handling guarantees

- Repository contents and issue text are **not** submitted to any provider for training. The
  provider allowlist is explicit configuration; an unknown provider host is refused.
- A `LocalProvider` path exists for environments that cannot send code to a third party; in that
  mode no repository bytes leave the deployment.
- Git author emails are stored **hashed with a per-repository salt** (`Repository`-scoped),
  never raw. The salt is generated at repo creation and stored with the row; it is not exported in
  reports.
- The AI request log stores provider, model, params, token counts, latency, and a redacted digest
  of untrusted prompt segments — never the raw body.
- Artifacts and DB rows are subject to retention policy (`DATA_MODEL.md` §4); `PERMANENT` items
  are the Trace, PR body, Benchmark results, and the final Patch.

---

## 6. Trust Report

Emitted on every terminal task (`VERIFIED` or `SAFE_STOP`) as a `PERMANENT` artifact; rendered in
the dashboard and includable in a PR body.

```
TrustReport
  task            id, repository, commit, task_type, title
  outcome         VERIFIED | SAFE_STOP | PARTIALLY_SUPPORTED
  evidence_trace  why_file[], why_change, why_tests[], why_safe        (from Verification)
  mapping         top candidates + evidence + overall_confidence
  plan_alignment  steps_implemented / total, unplanned_files[]
  tests           generated/executed/passed/failed/skipped/invalid; regression summary
  review          findings by severity; unresolved criticals (must be 0 for VERIFIED)
  scores          PCS {value, class, breakdown}; CRS {value, class, breakdown}; model_version
  replay          replay_fidelity, non_determinism_notes[]
  audit           audit_chain_range [seq_lo, seq_hi], verify_endpoint
  limitations     known_limitations[]
```

A human approver signs off from this one document.

---

## 7. Open questions

| # | Question | Resolution |
|---|---|---|
| G1 | external KMS / signing for the audit chain | MVP uses in-DB hash chain + PG privileges; external notarization is post-MVP |
| G2 | per-user vs per-API-key identity granularity | JWT subject in MVP; SSO/OIDC post-MVP |
| G3 | replay across provider version changes | manifest records model id; a provider-side model update is disclosed as a fidelity note |
