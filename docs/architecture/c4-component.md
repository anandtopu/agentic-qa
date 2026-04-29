# C4 — Component

Decomposes the four planes from PRD §11 into the components that ship in
Phase 0 / Phase 1. One owning team per component is named below; missing
ownership is itself a flag in design review.

## Control Plane (`apps/api`)

```mermaid
flowchart TB
  subgraph control[apps/api — qaforge_api]
    httpApi[FastAPI router\n/api/v1/*]
    webhookHandler[GitHub Webhook Receiver]
    authn[Auth — JWT / OIDC]
    workspaceSvc[Workspace Service]
    policySvc[Policy & Environment Service]
    approvalSvc[Approval Service]
    auditSvc[Audit Log Writer]
    flagsSvc[Feature Flag Client\nqaforge_api.flags]
    dbAccess[DB Layer\nqaforge_api.db]
    settings[Settings\npydantic-settings]
  end

  pg[(PostgreSQL)]
  redis[(Redis)]

  httpApi --> authn
  httpApi --> workspaceSvc
  httpApi --> policySvc
  httpApi --> approvalSvc
  httpApi --> auditSvc
  webhookHandler --> workspaceSvc
  workspaceSvc --> dbAccess
  policySvc --> dbAccess
  approvalSvc --> dbAccess
  auditSvc --> dbAccess
  flagsSvc -.read.-> settings
  dbAccess --> pg
  approvalSvc --> redis
```

| Component | Owning team | Notes |
|---|---|---|
| FastAPI router | Platform | PRD §13 surface |
| Webhook receiver | Platform | Signature-verified, tenant-scoped |
| Auth | Platform | OIDC + JWT (ADR-0008) |
| Workspace / Policy / Approval / Audit services | Platform | One module each under `apps/api/src/qaforge_api` |
| Feature Flag Client | Platform | Story 0.4.4 |
| DB Layer | Platform | SQLAlchemy 2.0 + Alembic (ADR-0007 RLS) |

## Intelligence Plane (`packages/agents`)

```mermaid
flowchart TB
  subgraph intel[packages/agents — qaforge_agents]
    orchestrator[LangGraph Orchestrator\nADR-0002]
    plannerAgent[Planner Agent]
    apiTestAgent[API Test Agent]
    uiTestAgent[UI Test Agent]
    dbAgent[DB Validation Agent]
    classifier[Failure Classifier]
    triage[Defect Triage]
    risk[Release Risk]
    reportAgent[Report Agent]
    policyGuard[Policy Guard]
    llmClient[LLMClient\nqaforge_agents.llm]
    recorder[Usage Recorder]
    promptReg[Prompt Templates]
  end

  toolRouter[Tool Router]
  llmProviders[LLM Providers\nADR-0004]
  pg[(PostgreSQL\nusage_records)]

  orchestrator --> plannerAgent
  orchestrator --> apiTestAgent
  orchestrator --> uiTestAgent
  orchestrator --> dbAgent
  orchestrator --> classifier
  orchestrator --> triage
  orchestrator --> risk
  orchestrator --> reportAgent
  orchestrator -. enforces .-> policyGuard
  plannerAgent --> llmClient
  apiTestAgent --> llmClient
  uiTestAgent --> llmClient
  classifier --> llmClient
  triage --> llmClient
  risk --> llmClient
  reportAgent --> llmClient
  llmClient --> llmProviders
  llmClient --> recorder
  recorder --> pg
  plannerAgent --> promptReg
  apiTestAgent --> toolRouter
  uiTestAgent --> toolRouter
  dbAgent --> toolRouter
```

| Component | Owning team | Notes |
|---|---|---|
| Orchestrator | ML eng | LangGraph behind facade (ADR-0002) |
| 10 specialised agents | ML eng | PRD §10.1; one module each — never collapse |
| LLMClient + Recorder | ML eng | Story 0.4.2 |
| Prompt templates | ML eng | Versioned in Phase 3 (Epic 3.4) |
| Policy Guard | Security + ML eng | Enforces PRD §10.3 + cost/runtime caps |

## Execution Plane (`packages/tools`)

```mermaid
flowchart TB
  subgraph exec[packages/tools — qaforge_tools]
    toolRouter[Tool Router\nresource limits + timeouts]
    apiRunner[API Test Runner\npytest + httpx]
    newmanRunner[Newman Runner\npostman/newman]
    uiRunner[Playwright Runner\nplaywright]
    sqlValidator[SQL Validator\nsqlalchemy]
    credBroker[Credential Broker\nADR-0008]
  end

  workerPool[Celery Workers\nADR-0003]
  objStore[(Object Store\nADR-0005)]
  vault[Secrets Manager]

  workerPool --> toolRouter
  toolRouter --> apiRunner
  toolRouter --> newmanRunner
  toolRouter --> uiRunner
  toolRouter --> sqlValidator
  toolRouter --> credBroker
  credBroker --> vault
  apiRunner --> objStore
  newmanRunner --> objStore
  uiRunner --> objStore
  sqlValidator --> objStore
```

| Component | Owning team | Notes |
|---|---|---|
| Tool Router | Platform | Per-tool resource limits, declared budgets |
| API/Newman/UI/DB runners | Platform | Each sandboxed; outputs SHA-256 keyed |
| Credential Broker | Security | Per-run ephemeral credentials; never logged |

## Evaluation Plane (`packages/eval`)

```mermaid
flowchart LR
  subgraph eval[packages/eval — qaforge_eval]
    runner[Eval Runner\nADR-0010]
    datasets[(Golden Datasets\nJSONL in repo)]
    scorers[Scorers\nper-dimension]
    scorecard[Scorecard JSON]
    baseline[Baseline\npinned on main]
  end

  llmClient[LLMClient]
  toolRouter[Tool Router\nfakes injected]
  ci[CI Gate]

  runner --> datasets
  runner --> llmClient
  runner --> toolRouter
  runner --> scorers
  scorers --> scorecard
  ci --> scorecard
  ci --> baseline
  ci -. blocks merge on regression .-> ci
```

| Component | Owning team | Notes |
|---|---|---|
| Runner | ML eng | Deterministic seeds; reuses prod LLMClient |
| Datasets | QA lead + ML eng | ≥ 50 cases per agent (Story 2.6.1) |
| Scorers | ML eng | Pluggable Python classes |
| CI gate | ML eng + SRE | Story 2.6.3 |

## Cross-cutting

```mermaid
flowchart LR
  app[Any service]
  otelCol[OpenTelemetry Collector]
  tempo[Tempo — traces]
  prom[Prometheus — metrics]
  loki[Loki — logs]
  grafana[Grafana]
  redaction[qaforge_redaction]

  app -- traces/metrics/logs --> otelCol
  app -- text-out passes through --> redaction
  otelCol --> tempo
  otelCol --> prom
  otelCol --> loki
  tempo & prom & loki --> grafana
```

| Component | Owning team | Notes |
|---|---|---|
| OpenTelemetry pipeline | SRE | ADR-0009 |
| Redaction utility | Security | Story 0.4.3 — applied at every text sink |
| Grafana dashboards | SRE | Version-controlled JSON in `infra/grafana/` |

## Data flows worth highlighting

- **PR analysis** (Phase 1 demo): GitHub webhook → Workspace Service → Orchestrator → Planner → API/UI Test Agents → Tool Router → Evidence (Object Store) → Failure Classifier → Report Agent → GitHub PR comment.
- **Approval-gated DB run** (Phase 2): Orchestrator pauses graph state, posts `approval_request`, Approval Service notifies Slack/email, approver clicks link → SSO → Approval Service resumes orchestrator via webhook.
- **Eval regression**: PR opens → CI runs `make eval` → Scorecard diff vs `main` baseline → block merge if dimension regressed > threshold.

## Conventions

- One owning team per component — leave no question of accountability.
- Components below the plane boundary are never imported across planes
  except via their public interface (the named class/module above).
- Component renames are an ADR-superseding event when the rename changes
  the public interface, not just the file.
