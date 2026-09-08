# AEGIS Security Model

Traceability: Specification §18, §21, §29, §34. Phase 0 deliverable (Spec §46 items 5, 6).
Companion to `AEGIS_IMPLEMENTATION_PLAN.md` §4.7–§4.8, §4.11, §4.14; `ADR-0010`, `ADR-0011`.

Status: Accepted — 2026-09-04. **Hardened and re-audited in Phase 26 (2026-09-08)** — see the
threat → control → test self-audit in §11. The `core/security/` package
(`pathjail`, `subprocess_guard`, `env_allowlist`, `ssrf`, `redaction`, `validate`) now exists as
the single enforcement point named in `ADR-0011`; `backend/tests/security/` is the threat suite.

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
| Malicious repo scripts / build hooks | Docker container; non-root UID; `--cap-drop ALL`; `--security-opt no-new-privileges`; clone with `core.hooksPath=/dev/null`, `--no-recurse-submodules` | `sandbox/policy.py`, `ingestion/git_client.py` |
| Shell execution / command injection | no `shell=True` anywhere; subprocess allowlist (`docker`, `git` only); all args as lists | `core/security/subprocess_guard.py` (`guarded_run` allowlist wrapper; `tests/security/test_subprocess_guard.py` scans for bypasses) |
| Filesystem escape / path traversal | `--read-only` rootfs + `tmpfs` scratch; only the task workspace bind-mounted `:rw`; host-side path jail (`safe_join`) resolves + asserts containment on every workspace fs op (`RWWorkspace.path_for`) | `sandbox/policy.py`, `core/security/pathjail.py` |
| Network exfiltration | `--network none` by default | `sandbox/policy.py` (asserted in tests) |
| SSRF (ingestion, GitHub) | URL scheme allowlist (`https`); host allowlist; block private / loopback / link-local IPs and DNS names resolving to them; block redirects to disallowed hosts | `core/security/ssrf.py` (re-exported by `ingestion/url_validator.py`), `github/client.py` |
| Dependency-install attacks | install is opt-in; host-allowlisted index; hash-pinned; runs in a network-restricted pre-step, not the test step | `sandbox/runner.py` |
| Credential / env-var theft | env scrubbed to an explicit allowlist before entering the container; no secret mounts; no Docker socket in the sandbox | `sandbox/policy.py`, `core/security/env_allowlist.py` |
| CPU / memory exhaustion | `--cpus`, `--memory`, `--memory-swap`; wall-clock timeout with SIGKILL | `sandbox/resource_limits.py` |
| Process spawning / fork bombs | `--pids-limit`; `--ulimit nproc`; `--ulimit nofile` | `sandbox/resource_limits.py` |
| Malicious tests / generated code | static safety scan (`eval`, `exec`, `compile`, `os.system`, `subprocess`, `socket`, `ctypes`, secret literals, `__import__`, escaping paths) **before** the file is written or run; still only ever executed in the sandbox | `testing/safety.py` (gate in `services/execution.py`, `services/repair.py`); `review/rules.py` for the post-hoc review |
| Container escape | minimal image; Docker default seccomp; no `--privileged`; no host Docker socket; `/tmp` tmpfs is `noexec,nosuid,nodev` + size-capped; image pinned by digest **when `sandbox_image_digest` is set** (tag-only otherwise -- open item §10) | `docker/sandbox.Dockerfile`, `sandbox/policy.py` |
| Supply chain | deps exact-pinned (`requirements.lock`); `bandit` + `pip-audit` CI gates; CycloneDX SBOM per build; lockfile-drift check. `--generate-hashes` is an open item (§10) | CI (`.github/workflows/ci.yml` `security` job) |
| Leftover state | container + volume always removed (`finally`); workspace GC; full execution logging | `sandbox/docker_backend.py` |

If Docker is unavailable, execution phases return `PARTIALLY_SUPPORTED{reason}` — **no host
fallback**. Stronger isolation (gVisor, Firecracker, nsjail) is a documented post-MVP option
(`ADR-0010`).

---

## 3. Input validation layer

`core/security/validate.py` is the entry-point facade for external-input validation, plus
`StrictModel` (`schemas/_base.py`) which every request body inherits so an unknown field is a
`422`, not a silent drop:

| Input | Checks | Where |
|---|---|---|
| Repository URL / path | scheme + host allowlist; SSRF; path canonicalisation; local path inside a configured root (re-checked in `git/repo_access.py`) | `core/security/ssrf.py` |
| Task / issue text | strip control + format chars; CRLF->LF; byte cap (truncate, provenance-recorded); markup/`SYSTEM:` prefixes kept **only as inert DB data**, never reaching a prompt | `services/tasks.py::normalize_text` |
| API request bodies | Pydantic `StrictModel` (`extra="forbid"`); `Content-Length` cap; a body-bearing request with no declared length -> `411` | `schemas/_base.py`, `main.py` |
| Uploaded xlsx | byte cap + declared-cell-count cap (decompression-bomb guard); sheet/column contract; per-row validation identical to the API path | `reporting/excel_import.py` |
| GitHub API payloads | consumed as data only (never a prompt); issue text goes through `normalize_text` on import | `github/provider.py` |
| AI JSON outputs | JSON-schema validation; **one repair round** (currently always single-shot -- `repair_fn` is unwired, see §10); then `FAILED` | `ai/schema_guard.py` |
| File paths from AI edit ops / generated tests | path-jail containment (`safe_join`) on write; escape -> recorded failed attempt | `core/security/pathjail.py`, `implementation/editor.py`, `testing/generator.py` |
| AI-generated test code | pre-execution static scan: no `eval`/`exec`/`compile`/`__import__`/`os.system`/`subprocess`/`socket`/`ctypes`, no secret literal, no escaping path | `testing/safety.py` (gate in `services/execution.py` + `services/repair.py`) |

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
- `backend/tests/security/test_secret_scan.py` runs an ingest+analyze slice and asserts no
  secret-shaped content lands in any log record or `artifacts_root` file; it runs in normal CI
  (not deselected) as a hard gate.

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

_Design:_ `AuditLog` rows form a hash chain: `entry_hash = sha256(seq || prev_hash || actor ||
action || target_type || target_id || payload_digest || created_at)`; a `GET /audit/verify`
endpoint walks the chain and reports the first break; rows are append-only. Full spec in
`GOVERNANCE.md` §2/§3.

_Status:_ **the `audit_log` table shape exists; the hash chain, the write path, and
`/audit/verify` are deferred to a dedicated follow-up** (see §10). No row is written yet.

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
| **Tamper-evident audit chain not yet built** | table shape only; `AuditLog` has no writers, no `/audit/verify` | Phase 26 deferred it to a dedicated follow-up (chain hash + seq allocation + payload redaction + wiring + append-only migration + tests) |
| **Sandbox image tag-pinned, not digest-pinned by default** | no image registry / CI publish pipeline yet | `sandbox_image_digest` setting is honoured today; digest-by-default lands with the image-publish pipeline |
| **Dependencies exact-pinned but not `--hash`-pinned** | `pip-compile --generate-hashes` interacts badly with the hand-patched `pywin32` win32 marker (`CONTRIBUTING.md`) | `pip-audit` CI gate covers known CVEs; `--generate-hashes` is a follow-up |
| **`schema_guard` repair round is unwired** | every caller passes `repair_fn=None`; effective behaviour is single-shot validate-or-`FAILED` | acceptable (fail-closed); wiring a real `repair_fn` is a follow-up |

---

## 11. Phase 26 threat -> control -> test self-audit

Every row has a control in code and a test in `backend/tests/security/` (runs in normal CI).

| Threat (Spec §18/§34) | Control (module) | Test |
|---|---|---|
| Path traversal / workspace escape via AI `EditOp.path` / `TestCaseAI.path` | `core/security/pathjail.safe_join`, enforced in `RWWorkspace.path_for` | `test_pathjail.py` |
| Command injection / `shell=True` / arbitrary exec | `core/security/subprocess_guard.guarded_run` (allowlist, no shell); 3 sanctioned call sites | `test_subprocess_guard.py` (incl. AST scan for bypasses) |
| Malicious generated test code (`eval`/`exec`/`socket`/`subprocess`/secret literal) | `testing/safety.scan_generated_cases`, gate in `services/execution.py` + `services/repair.py` | `test_generated_code_scan.py` |
| SSRF / private-IP / DNS-rebind / IDN / look-alike host | `core/security/ssrf` (re-export shim `ingestion/url_validator.py`) | `test_ssrf.py`, `test_url_validator.py` |
| Malicious repository (git hooks, exfil test, fork bomb, symlink escape) | `ingestion/git_client` hardening + local materialise ignores `.git`; Docker sandbox for execution | `test_malicious_repo.py` |
| Unbounded / unknown-field request bodies; xlsx decompression bomb | `StrictModel`, `main.py` body-size + `411`, `reporting/excel_import` byte/cell caps | `test_request_validation.py` |
| API abuse / request flooding | `core/ratelimit.RateLimiter` + `main.py` middleware (opt-in) | `test_rate_limit.py` |
| Secret leakage into logs / artifacts | `core/security/redaction` + `core/logging` filter; `core/security/env_allowlist.scrub_secret_env` for the local runner | `test_secret_scan.py`, `test_logging_redaction.py`, `test_github_redaction.py` |
| Credential theft via env into sandbox | Docker env `= {}`; local fake runner env scrubbed by name pattern | `test_secret_scan.py::test_scrub_secret_env_drops_credential_shaped_names` |
| Supply chain | `bandit` + `pip-audit` + SBOM + lockfile-drift CI gates | `.github/workflows/ci.yml` `security` job |
