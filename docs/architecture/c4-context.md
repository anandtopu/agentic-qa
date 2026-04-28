# C4 — Context

```mermaid
flowchart LR
  subgraph users[Users]
    qae[QA Engineer]
    dev[Developer]
    rm[Release Manager]
  end

  subgraph qaforge[QAForge AI]
    web[Web Dashboard]
    api[API / Control Plane]
    orch[Workflow Orchestrator]
    agents[Agent Runtime]
    tools[Tool Execution Layer]
    store[(Evidence + Results Store)]
  end

  subgraph external[External systems]
    gh[GitHub Actions / Webhooks]
    llm[LLM Providers]
    jira[Jira]
    slack[Slack / Email]
    grafana[Grafana / OTel]
  end

  qae --> web
  dev --> web
  rm  --> web
  web --> api
  api --> orch
  orch --> agents
  agents --> tools
  agents --> llm
  tools --> store
  api --> store
  gh -- webhooks --> api
  api -- PR comments --> gh
  agents -- approvals --> slack
  api -- issue creation --> jira
  api --> grafana
  agents --> grafana
```

## Notes

- **Trust boundary** at the API and the GitHub webhook receiver — both
  validate signatures and apply tenant scoping.
- **Tool execution** is sandboxed (process or container) and never shares
  credentials with the agent layer directly; tools resolve credentials
  through a typed broker.
- **Evidence store** is write-once and content-addressed; no service has
  delete authority outside the retention sweeper.
