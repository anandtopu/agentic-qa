# Architecture Decision Records

Lightweight, append-only decision log. New ADRs follow the template in
[`_template.md`](_template.md). Numbering is monotonic and never reused.

| # | Title | Status | Decided |
|---|---|---|---|
| [0001](0001-backend-language-and-framework.md) | Backend language & framework | Accepted | 2026-04-27 |
| [0002](0002-agent-orchestration-runtime.md) | Agent orchestration runtime | Accepted | 2026-04-28 |
| [0003](0003-workflow-engine.md) | Workflow engine (Celery vs. Temporal) | Accepted | 2026-04-28 |
| [0004](0004-llm-provider-abstraction.md) | LLM provider abstraction & default model | Accepted | 2026-04-28 |
| [0005](0005-object-storage.md) | Object storage (MinIO local, S3/GCS prod) | Accepted | 2026-04-28 |
| [0006](0006-frontend-stack.md) | Frontend stack | Accepted | 2026-04-28 |
| [0007](0007-multi-tenancy-model.md) | Multi-tenancy model | Accepted | 2026-04-28 |
| [0008](0008-secrets-management.md) | Secrets management | Accepted | 2026-04-28 |
| [0009](0009-telemetry-stack.md) | Telemetry stack (OpenTelemetry + Grafana) | Accepted | 2026-04-28 |
| [0010](0010-evaluation-harness-design.md) | Evaluation harness design | Accepted | 2026-04-28 |

## Conventions

- One file per decision: `NNNN-kebab-title.md`.
- States: `Proposed` → `Accepted` → `Superseded by NNNN` → `Deprecated`.
- Never edit an Accepted ADR's decision body — supersede with a new one.
- Each ADR records: Context, Decision, Consequences, Alternatives.
- Every PR that changes architecture must touch (or add) an ADR.
