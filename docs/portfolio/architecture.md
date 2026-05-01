# Architecture diagrams

The detailed C4 set lives under [`docs/architecture/`](../architecture):
[context](../architecture/c4-context.md), [container](../architecture/c4-container.md),
[component](../architecture/c4-component.md), and the [ERD](../architecture/erd.md).
This page is the portfolio-friendly reading guide — every diagram below is
mermaid so it renders inline on GitHub.

## Four planes (PRD §11)

```mermaid
flowchart TB
  subgraph control[Control Plane — apps/api]
    cp1[Workspaces / users / policies]
    cp2[Approvals · Audit · Usage / cost]
    cp3[Prompt pins · Flakiness · External issues]
  end

  subgraph intel[Intelligence Plane — packages/agents]
    ip1[Planner]
    ip2[API · UI · DB · Integration testers]
    ip3[Classifier · Triage · Risk · Reporter]
    ip4[Policy Guard]
  end

  subgraph exec[Execution Plane — packages/tools]
    ep1[Playwright runner]
    ep2[Newman / pytest+httpx]
    ep3[SQL validator]
    ep4[Tool router · resource-bounded sandbox]
  end

  subgraph eval[Evaluation Plane — packages/eval]
    vp1[Golden datasets]
    vp2[Per-dimension scorers]
    vp3[Scorecard · regression gate]
  end

  control --> intel
  intel -- tools --> exec
  intel --> eval
  exec --> control
```

Each plane sits in its own package; cross-plane code is a smell — `CLAUDE.md`
keeps the boundary.

## Orchestration sequence (PRD §10.2)

```mermaid
sequenceDiagram
  autonumber
  participant Orch as Workflow Orchestrator
  participant Plan as Agent Task Planner
  participant Router as Tool Router
  participant Exec as Tool Executor
  participant Store as Evidence Store
  participant Evalr as Evaluator
  participant Approve as Human Approval Service
  participant Report as Report Generator

  Orch->>Plan: build agent-task graph
  Plan->>Router: dispatch tool calls
  Router->>Exec: invoke (sandboxed)
  Exec->>Store: write artifacts (SHA-256 keyed)
  Store-->>Evalr: score evidence
  Evalr-->>Approve: gate if policy says so
  Approve-->>Orch: resume / abort
  Orch->>Report: render evidence report
```

Story 1.6.1 ships the runtime; Story 4.3 wraps each step in a circuit breaker
+ bulkhead.

## PR analysis flow (Phase 1 demo)

```mermaid
sequenceDiagram
  autonumber
  actor Dev as Developer
  participant GH as GitHub
  participant API as aqao-api / Webhook
  participant Orch as Orchestrator
  participant Planner
  participant Agents as API + UI agents
  participant Tools as Tool Router
  participant Store as Evidence Store
  participant Class as Failure Classifier
  participant Report as Report Agent

  Dev->>GH: open PR
  GH->>API: webhook (HMAC signed)
  API->>Orch: start run (idempotency key)
  Orch->>Planner: plan from diff + OpenAPI / user stories
  Planner-->>Orch: test plan
  Orch->>Agents: execute API + UI cases
  Agents->>Tools: dispatch (Playwright / Newman / pytest)
  Tools->>Store: artifacts + logs (redacted)
  Store-->>Class: failures → 5-category classification
  Class-->>Report: merge results + drivers
  Report-->>API: signed-URL report
  API-->>GH: PR comment + quality gate
```

## Approval-gated DB run (Phase 2)

```mermaid
sequenceDiagram
  autonumber
  participant Orch as Orchestrator
  participant DB as DB Validation Agent
  participant Guard as Policy Guard
  participant Approve as Approval Service
  participant Slack as Slack / Email
  actor Approver

  Orch->>DB: validate snapshot diff
  DB->>Guard: destructive SQL detected
  Guard->>Approve: raise approval_request (paused)
  Approve->>Slack: notify approver
  Slack->>Approver: link
  Approver->>Approve: SSO + decision
  Approve-->>Orch: webhook resume / abort
  Orch->>DB: continue (read-only fallback if denied)
```

Approval gates are required for: destructive SQL, production-environment
tests, external Jira/GitHub issue creation, release readiness sign-off, CI
pipeline modifications, high-cost eval runs (PRD §9.10).

## Eval regression gate

```mermaid
sequenceDiagram
  autonumber
  actor Dev
  participant CI
  participant Eval as Eval Harness
  participant Base as Pinned baseline (main)
  participant Score as Scorecard

  Dev->>CI: push branch / open PR
  CI->>Eval: make eval (deterministic seeds)
  Eval->>Score: per-dimension scorecard
  Score->>Base: diff vs main
  Base-->>CI: regression > threshold?
  alt regression
    CI-->>Dev: block merge
  else no regression
    CI-->>Dev: allow merge
  end
```

## Deployment topology (production / Helm)

```mermaid
flowchart TB
  internet([Internet])
  github([GitHub])
  llm([LLM provider])
  obs([Tempo · Prom · Loki · Grafana])

  subgraph cluster[Kubernetes cluster — Helm chart]
    ingress[Ingress · TLS termination]
    subgraph apiNs[Namespace: aqao]
      apiPod[API pods · FastAPI]
      orchPod[Orchestrator pods]
      agentPod[Agent runtime pods]
      workerPod[Tool worker pods · sandboxed]
      otelCol[OTel Collector]
    end
  end

  subgraph data[Managed data services]
    rds[(PostgreSQL · RDS)]
    redis[(Redis · ElastiCache)]
    s3[(Object store · S3 / MinIO)]
    sm[(Secrets Manager · IRSA)]
  end

  internet --> ingress
  ingress --> apiPod
  github -- signed webhooks --> apiPod
  apiPod --> orchPod
  orchPod --> agentPod
  agentPod --> workerPod
  agentPod -- egress allowlist --> llm
  apiPod --> rds
  apiPod --> redis
  workerPod --> s3
  apiPod --> sm
  apiPod & orchPod & agentPod & workerPod --> otelCol
  otelCol --> obs
```

Terraform modules + Helm chart in [`infra/helm/`](../../infra/helm/);
GCP Cloud SQL Auth Proxy uses an `extraContainers` sidecar (TD-014).

## Data model

ERD lives at [`docs/architecture/erd.md`](../architecture/erd.md) in
mermaid `erDiagram` form. Highlights:

* Tenant-scoped tables enforce **row-level security** with
  `FORCE ROW LEVEL SECURITY` (ADR-0007).
* The audit log is append-only with HMAC-SHA256 signatures (Story 2.4.1).
* `external_issues` links defects to Jira/GitHub issues with a 24h dedup
  window (Story 3.2.1).
* `prompt_pins` per-workspace overrides the in-code prompt registry
  (Story 3.4.1).

## Trust boundaries

See [`docs/security/threat-model.md`](../security/threat-model.md) for the
full STRIDE matrix. The four crossings worth highlighting:

```mermaid
flowchart LR
  net([Internet]) -->|TLS| lb[Ingress LB]
  lb -->|Pod Security: restricted| api[API pods]
  gh([GitHub]) -->|HMAC signed| api
  api -->|IRSA scoped to workspace| aws[(AWS Secrets / S3 / RDS)]
  agents[Agents] -->|NetworkPolicy egress allowlist| llm([LLM provider])
```

1. **Internet → Ingress LB → API pods** — TLS-terminated; Pod Security
   restricted profile (Story 3.6.2).
2. **GitHub → /api/v1/webhooks** — HMAC-signed (Story 1.2.1).
3. **API pods → AWS Secrets Manager / S3 / RDS** — IRSA (Story 3.6.1) with
   policies scoped to the workspace's resources.
4. **Agents → LLM provider** — egress allowlist via NetworkPolicy
   (Story 3.6.2); circuit-breaker + heuristic fallback when the provider is
   down (Story 4.3).

## ADR index

| ADR | Topic | Phase |
|---|---|---|
| 0001 | Pydantic v2 + extra=forbid for control-plane bodies | 0 |
| 0002 | LangGraph behind an internal facade | 0 |
| 0003 | Agent-task graph as the unit of orchestration | 1 |
| 0004 | LLM provider abstraction | 0 |
| 0005 | Object storage choice | 0 |
| 0006 | Frontend stack | 0 |
| 0007 | Postgres RLS + FORCE ROW LEVEL SECURITY | 1 |
| 0008 | Secrets management | 0 |
| 0009 | Telemetry stack | 0 |
| 0010 | Custom Python eval harness (no LangSmith) | 2 |

ADR sources are in [`docs/adr/`](../adr); template at `_template.md`.
