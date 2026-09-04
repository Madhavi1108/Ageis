# AEGIS Security Model

Traceability: Specification §18, §21, §29, §34. Phase 0 deliverable (Spec §46 items 5, 6).
Companion to `AEGIS_IMPLEMENTATION_PLAN.md` §4.7–§4.8, §4.11, §4.14; `ADR-0010`, `ADR-0011`.

Status: Accepted — 2026-09-04. Hardened and re-audited in Phase 26.

---

## 1. Assets and trust model

| Asset | Trust | Protection goal |
|---|---|---|
| AEGIS source, config, database | Trusted | integrity, availability |
| AI provider API keys, GitHub tokens | Secret | never logged, never persisted, never enter the sandbox |
| Target repository contents (files, tests, config, Git metadata) | **Untrusted** | must not execute on the host; must not exfiltrate; must not escape the workspace |
| AI provider outputs (plans, edit ops, RCA, reviews, JSON) | **Untrusted** | schema-validated; no `eval`/`exec`; no unchecked filesystem paths |
| Issue / task text | **Untrusted** | never concatenated into a system prompt; sanitized structured fields only |
| Generated patches and generated tests | **Untrusted** | executed only in the sandbox; static safety scan first |

Rule (Spec §34): **never trust** repository files, Git metadata, AI outputs, issue descriptions,
generated patches, or test code.

---

## 2. Sandbox threat -> control matrix (Spec §18, §34)

| Threat | Control | Enforcement point |
|---|---|---|
| Malicious repo scripts / build hooks | Docker container; non-root UID; `--cap-drop ALL`; `--security-opt no-new-privileges`; clone with `core.hooksPath=/dev/null`, `--no-recurse-submodules` | `sandbox/policy.py`, `repository/git_client.py` |
| Shell execution / command injection | no `shell=True` anywhere; subprocess allowlist (`docker`, `git` only); all args as lists | `core/security/subprocess_guard.py` (import-time lint + runtime wrapper) |
| Filesystem escape / path traversal | `--read-only` rootfs + `tmpfs` scratch; only the task workspace bind-mounted `:rw`; host-side path-jail resolves + asserts containment before any fs op | `sandbox/policy.py`, `core/security/pathjail.py` |
| Network exfiltration | `--network none` by default | `sandbox/policy.py` (asserted in tests) |
| SSRF (ingestion, GitHub) | URL scheme allowlist (`https`); host allowlist; block private / loopback / link-local IPs and DNS names resolving to them; block redirects to disallowed hosts | `repository/url_validator.py`, `github/client.py` |
| Dependency-install attacks | install is opt-in; host-allowlisted index; hash-pinned; runs in a network-restricted pre-step, not the test step | `sandbox/runner.py` |
| Credential / env-var theft | env scrubbed to an explicit allowlist before entering the container; no secret mounts; no Docker socket in the sandbox | `sandbox/policy.py`, `core/security/env_allowlist.py` |
| CPU / memory exhaustion | `--cpus`, `--memory`, `--memory-swap`; wall-clock timeout with SIGKILL | `sandbox/resource_limits.py` |
| Process spawning / fork bombs | `--pids-limit`; `--ulimit nproc`; `--ulimit nofile` | `sandbox/resource_limits.py` |
| Malicious tests / generated code | static safety rules (`eval`, `exec`, `compile`, `os.system`, `subprocess`, `socket`, secret-like literals, `__import__`) flagged before execution; still only ever run in the sandbox | `review/rules.py`, `sandbox/runner.py` |
| Container escape | base image pinned by **digest**; minimal image (no compilers unless needed); seccomp default profile (custom profile optional); no `--privileged`; no host Docker socket; rootless daemon where available | `docker/sandbox.Dockerfile`, `sandbox/policy.py` |
| Supply chain | pinned + hashed deps; `pip-audit` CI gate; SBOM per build; sandbox image scanned before promotion | CI |
| Leftover state | container + volume always removed (`finally`); workspace GC; full execution logging | `sandbox/docker_backend.py` |

If Docker is unavailable, execution phases return `PARTIALLY_SUPPORTED{reason}` — **no host
fallback**. Stronger isolation (gVisor, Firecracker, nsjail) is a documented post-MVP option
(`ADR-0010`).

---

## 3. Input validation layer

A single `core/security/validate.py` module is the entry gate for every external input:

| Input | Checks |
|---|---|
| Repository URL / path | scheme + host allowlist; SSRF; path canonicalisation; local path must be inside a configured roots list |
| Task / issue text | strip control chars; max length; reject template/markup that could reach a prompt; store only sanitized fields |
| API request bodies | Pydantic schema; size limits; enum validation; no unknown fields |
| Uploaded xlsx | size cap; sheet/column contract; per-row validation identical to the API path |
| GitHub webhook / API payloads | schema validation; treat every string as data |
| AI JSON outputs | JSON-schema validation (`ai/schema_guard.py`); one repair round; then `FAILED` |
| File paths from AI edit ops | path-jail containment check; must be within the plan's allowed set |

---

## 4. Secret handling

- Secrets come only from process environment / a secrets file; never written to the DB or an
  artifact.
- `core/logging.py` installs a redaction filter: known key patterns (`*_API_KEY`, `*_TOKEN`,
  `authorization`, bearer strings, `gh[pousr]_...`, base64-looking long strings adjacent to
  secret keys) are masked in every log record and every structured error.
- AI request logging stores only: provider, model id, params, token counts, latency, and a
  **redacted digest** of any prompt segment containing untrusted content — never the full prompt
  body with repo/issue text.
- A CI test scans logs and artifacts produced by the test suite for secret patterns and fails on
  a hit. Re-run as a hard gate in Phase 26.

---

## 5. RBAC (Spec §29; detail in `GOVERNANCE.md`)

| Role | Can |
|---|---|
| `viewer` | read tasks, timelines, plans, diffs, reports |
| `operator` | + create / run / cancel tasks, ingest repositories |
| `approver` | + resolve `AWAITING_APPROVAL`, override a scope or risk gate (with a recorded reason) |
| `admin` | + manage providers, policy, limits, users |

Every mutating route declares its required role. Overrides are always `AuditLog`-recorded with the
actor, the gate, and the reason.

---

## 6. Human-in-the-loop policy (Spec §29)

Per-action policy value `AUTO` / `REVIEW_REQUIRED` / `BLOCKED`, from configurable rules.

- `AUTO` (default): analyse, plan, generate tests, run sandbox tests, generate a local patch.
- `REVIEW_REQUIRED`: modify a protected branch, create an external PR, upgrade a dependency, run a
  DB migration, `CRS >= HIGH`, `PCS < 70`. -> task parks in `AWAITING_APPROVAL`.
- `BLOCKED`: destructive operations, unresolved scope violation, unresolved `CRITICAL` finding.

---

## 7. Tamper-evident audit chain

`AuditLog` rows form a hash chain: `entry_hash = sha256(seq || prev_hash || actor || action ||
target_type || target_id || payload_digest || created_at)`. A `GET /audit/verify` endpoint walks
the chain and reports the first break, if any. Rows are append-only (no update, no delete at the
ORM or the DB-permission level). Full spec in `GOVERNANCE.md` §2.

---

## 8. AI-output distrust (Spec §21)

- Every AI conclusion is tagged `FACT` / `INFERENCE` / `HYPOTHESIS` / `RECOMMENDATION`; missing
  info is `UNKNOWN`; weak evidence is `LOW CONFIDENCE`.
- A `FACT` must cite at least one re-checkable `Evidence` item.
- Sandbox execution results override any AI claim.
- AI-produced code is never `exec`'d in-process; AI-produced paths are jailed; AI-produced shell
  strings are rejected.

---

## 9. Data-handling guarantees

- Repository contents and issue text are **not** submitted to any provider for training; the
  provider allowlist is explicit configuration.
- A `LocalProvider` path exists for environments that cannot send code to a third party.
- Author emails from Git are stored **hashed with a per-repository salt**, never raw.
- Deterministic-replay metadata records provider + model + params + seed, not prompt bodies.

---

## 10. Residual risks (documented, accepted for MVP)

| Risk | Why accepted | Mitigation / future |
|---|---|---|
| Docker is not a security boundary as strong as a VM | Spec's preferred MVP; full cap-drop + no-net + non-root + pids/mem caps cover the threat model | gVisor / Firecracker / nsjail post-MVP (`ADR-0010`) |
| A frontier model could emit a subtly malicious but schema-valid patch | schema validity != safety | static safety scan + code review + sandbox execution + scope guard + human approval on risky patches |
| Supply-chain compromise of a pinned dependency | pinning + hashing + audit reduce, do not eliminate | SBOM, scheduled re-audit, minimal dependency surface |
| Side channels from the sandbox (timing, resource) | low value target for the MVP | out of scope; noted |
