# Architecture Decision Records

Lightweight, append-only decision log. New ADRs follow the template in
[`_template.md`](_template.md). Numbering is monotonic and never reused.

| # | Title | Status | Decided |
|---|---|---|---|
| [0001](0001-backend-language-and-framework.md) | Backend language & framework | Accepted | 2026-04-27 |
| 0002 | Agent orchestration runtime | Proposed | — |
| 0003 | Workflow engine (Celery vs. Temporal) | Proposed | — |
| 0004 | LLM provider abstraction & default model | Proposed | — |
| 0005 | Object storage (MinIO local, S3/GCS prod) | Proposed | — |
| 0006 | Frontend stack | Proposed | — |
| 0007 | Multi-tenancy model | Proposed | — |
| 0008 | Secrets management | Proposed | — |
| 0009 | Telemetry stack (OpenTelemetry + Grafana) | Proposed | — |
| 0010 | Evaluation harness design | Proposed | — |

## Conventions

- One file per decision: `NNNN-kebab-title.md`.
- States: `Proposed` → `Accepted` → `Superseded by NNNN` → `Deprecated`.
- Never edit an Accepted ADR's decision body — supersede with a new one.
- Each ADR records: Context, Decision, Consequences, Alternatives.
- Every PR that changes architecture must touch (or add) an ADR.
