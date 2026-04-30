# Architecture diagrams

Existing diagrams live under [`docs/architecture/`](../architecture).
This page is the portfolio-friendly reading guide.

## Four planes (PRD §11)

```text
┌────────────────────────────────────────────────────────────────┐
│                       Control Plane                             │
│  apps/api ─ workspaces, users, policies, environments, audit   │
│  approvals, usage/cost, prompt pins, flakiness, external issues │
└──────────┬───────────────────────────────────┬─────────────────┘
           │                                   │
           ▼                                   ▼
┌──────────────────────┐         ┌────────────────────────────────┐
│  Intelligence Plane  │         │       Execution Plane          │
│  packages/agents     │  tools  │  packages/tools                │
│  Planner / API tester│ ────────│  Playwright / Newman / pytest  │
│  UI tester / DB val. │         │  Subprocess + Stub flavours    │
│  Failure classifier  │         │  Sandboxed, resource-bounded   │
│  Reporter / Risk     │         └────────────────────────────────┘
└──────────┬───────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────────┐
│                     Evaluation Plane                            │
│  packages/eval ─ scorers, datasets, runner, gate, trend store   │
└────────────────────────────────────────────────────────────────┘
```

Each plane sits in its own package; cross-plane code is a smell
(CLAUDE.md keeps the boundary).

## Orchestration sequence (PRD §10.2)

```text
Workflow Orchestrator
  → Agent Task Planner
  → Tool Router
  → Tool Executor
  → Evidence Store
  → Evaluator
  → Human Approval Service
  → Report Generator
```

Story 1.6.1 ships the runtime; Story 4.3 wraps each step in a circuit
breaker + bulkhead.

## Data model

ERD lives at [`docs/architecture/erd.md`](../architecture/erd.md).
Highlights:

* Tenant-scoped tables enforce **row-level security** with
  `FORCE ROW LEVEL SECURITY` (ADR-0007).
* The audit log is append-only with HMAC-SHA256 signatures (Story
  2.4.1).
* `external_issues` links defects to Jira/GitHub issues with a 24h
  dedup window (Story 3.2.1).
* `prompt_pins` per-workspace overrides the in-code prompt registry
  (Story 3.4.1).

## Trust boundaries

See [`docs/security/threat-model.md`](../security/threat-model.md)
for the full STRIDE matrix. The four crossings worth highlighting:

1. **Internet → Ingress LB → API pods** — TLS-terminated; Pod
   Security restricted profile (Story 3.6.2).
2. **GitHub → /api/v1/webhooks** — HMAC-signed (Story 1.2.1).
3. **API pods → AWS Secrets Manager / S3 / RDS** — IRSA
   (Story 3.6.1) with policies scoped to the workspace's resources.
4. **Agents → LLM provider** — egress allowlist via NetworkPolicy
   (Story 3.6.2); circuit-breaker + heuristic fallback when the
   provider is down (Story 4.3).

## ADR index

| ADR | Topic | Phase |
|---|---|---|
| 0001 | Pydantic v2 + extra=forbid for control-plane bodies | 0 |
| 0002 | LangGraph behind an internal facade | 0 |
| 0003 | Agent-task graph as the unit of orchestration | 1 |
| 0007 | Postgres RLS + FORCE ROW LEVEL SECURITY | 1 |
| 0010 | Custom Python eval harness (no LangSmith) | 2 |

(ADR sources are in [`docs/adr/`](../adr); template at
`_template.md`.)
