# C4 — Container

Maps the four planes from PRD §11 to containers.

```mermaid
flowchart TB
  subgraph control[Control Plane]
    api[FastAPI / aqao-api]
    db[(PostgreSQL)]
    cache[(Redis)]
  end

  subgraph intel[Intelligence Plane]
    orch[Orchestrator (Celery / Temporal)]
    agentRuntime[Agent Runtime (aqao-agents)]
    promptReg[Prompt Registry]
  end

  subgraph exec[Execution Plane]
    apiRunner[API Test Runner]
    uiRunner[Playwright Runner]
    dbRunner[DB Validator]
    toolBroker[Tool Broker]
  end

  subgraph eval[Evaluation Plane]
    evalHarness[Eval Harness (aqao-eval)]
    goldenDS[(Golden Datasets)]
    scoreboard[Scoreboard]
  end

  subgraph storage[Shared]
    objStore[(Object Store — MinIO / S3)]
    otel[OpenTelemetry Collector]
  end

  api --> db
  api --> cache
  api --> orch
  orch --> agentRuntime
  agentRuntime --> promptReg
  agentRuntime --> toolBroker
  toolBroker --> apiRunner
  toolBroker --> uiRunner
  toolBroker --> dbRunner
  apiRunner --> objStore
  uiRunner --> objStore
  dbRunner --> objStore
  evalHarness --> agentRuntime
  evalHarness --> goldenDS
  evalHarness --> scoreboard

  api & orch & agentRuntime & toolBroker --> otel
```
