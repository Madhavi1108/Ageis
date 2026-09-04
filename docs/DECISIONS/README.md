# Architecture Decision Records

Traceability: Specification §51 (early architectural decisions). Phase 0 deliverable.

Each ADR records one decision. Format:

```
# ADR-NNNN: <title>
Status: Proposed | Accepted | Superseded by ADR-MMMM
Date: YYYY-MM-DD
Deciders: Phase 0
## Context
## Decision
## Consequences
## Alternatives considered
```

Rule: **a decided ADR is never edited** (beyond fixing typos). A change of mind means a new ADR
that supersedes it, and the old one's `Status` is updated to point at the successor.

## Index

| ADR | Decision | Spec §51 item |
|---|---|---|
| [ADR-0001](ADR-0001-database-schema.md) | Database schema & SQLite→PostgreSQL portability | database schema |
| [ADR-0002](ADR-0002-analysis-state-machine.md) | Workflow / analysis state machine | analysis state machine |
| [ADR-0003](ADR-0003-job-model.md) | Job & worker model | job model |
| [ADR-0004](ADR-0004-agent-orchestration.md) | Agent orchestration model | agent orchestration model |
| [ADR-0005](ADR-0005-ai-provider-abstraction.md) | AI provider abstraction | AI provider abstraction |
| [ADR-0006](ADR-0006-repository-abstraction.md) | Repository abstraction | repository abstraction |
| [ADR-0007](ADR-0007-code-analysis-abstraction.md) | Code-analysis & graph abstraction | code-analysis abstraction |
| [ADR-0008](ADR-0008-patch-representation.md) | Patch representation | patch representation |
| [ADR-0009](ADR-0009-artifact-storage.md) | Artifact storage | artifact storage |
| [ADR-0010](ADR-0010-sandbox-architecture.md) | Sandbox architecture | sandbox architecture |
| [ADR-0011](ADR-0011-security-policy.md) | Security policy | security policy |
| [ADR-0012](ADR-0012-repository-limits.md) | Repository & analysis limits | repository limits |
| [ADR-0013](ADR-0013-test-execution-model.md) | Test execution model | test execution model |
| [ADR-0014](ADR-0014-git-strategy.md) | Git strategy | Git strategy |
| [ADR-0015](ADR-0015-github-strategy.md) | GitHub strategy | GitHub strategy |
| [ADR-0016](ADR-0016-memory-architecture.md) | Engineering-memory architecture | memory architecture |
| [ADR-0017](ADR-0017-metric-algorithms.md) | Metric & scoring algorithms | metric algorithms |
| [ADR-0018](ADR-0018-frontend-state-model.md) | Frontend state model | frontend state model |
| [ADR-0019](ADR-0019-model-routing.md) | Model-routing policy (cheap/frontier) | (plan addition) |
| [ADR-0020](ADR-0020-capability-floors.md) | Capability-floor thresholds & decision gates | (plan addition) |
