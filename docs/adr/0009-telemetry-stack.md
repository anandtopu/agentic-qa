# ADR-0009: Telemetry stack — OpenTelemetry, Prometheus, Tempo, Loki, Grafana

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Tech lead
- **Consulted:** SRE
- **Informed:** All eng

## Context

PRD §14.4 demands tracing every agent step, structured logging with redaction, latency by workflow stage, and token/cost tracking. Story 0.4.1 already specifies "structlog JSON logging, OpenTelemetry tracing, Prometheus metrics, Grafana dashboards" — this ADR pins the concrete choices and the data model.

A Agentic QA Orchestrator run spans Web → API → Celery worker → LangGraph node → LLM provider → Tool subprocess. A single trace must connect them or we lose the ability to debug latency or attribute cost.

## Decision

Use **OpenTelemetry SDKs** (Python and TypeScript) as the only instrumentation API. Backends:

- **Traces** — OpenTelemetry Collector → **Grafana Tempo**. One trace per workflow, propagated via W3C `traceparent` and our own `aqao_trace_id` (request-scoped UUID generated at the edge).
- **Metrics** — OpenTelemetry Collector → **Prometheus**. Histograms for latency by stage; counters for runs, failures, retries; gauges for queue depth.
- **Logs** — `structlog` in Python and `pino` in Node; emitted as JSON; OpenTelemetry Collector → **Loki**. Logs include `trace_id`, `span_id`, `tenant_id`, `workspace_id`, `run_id`, `correlation_id`.
- **Visualisation** — **Grafana** (already used elsewhere in the stack); dashboards version-controlled as JSON in `infra/grafana/`.
- **Cost** is **not** a Prometheus metric long-term — it's persisted to `usage_records` (PRD §12) for accurate billing math; Prometheus carries a sampled cost gauge for live dashboards.

Standard span attributes (every agent/tool span sets them):

```
aqao.tenant_id, aqao.workspace_id, aqao.run_id,
aqao.agent, aqao.tool, aqao.model,
aqao.tokens.prompt, aqao.tokens.completion,
aqao.usd_cost, aqao.policy.gate
```

Sampling: 100% for traces in dev/staging; head-based sampling in prod at 10%, with **always-sample** for traces that touch an approval gate or exceed cost/runtime budgets. Logs are unsampled.

## Consequences

- **Positive:** vendor-neutral via OTel; Grafana stack is open-source and portable across AWS/GCP; one query language (PromQL/LogQL/TraceQL) per signal type; SLO dashboards in Phase 4 plug in directly.
- **Negative:** running Tempo + Prometheus + Loki in cluster adds operational surface; for self-hosted demo deployments, we'll ship a `dev` profile that uses local file exporters instead of the full backend.
- **Neutral:** observability cost is a real line item — sampling and retention (30-day traces, 90-day metrics, 14-day logs) need quarterly review.

## Alternatives considered

- **Datadog / New Relic / Honeycomb** — superb DX, vendor lock-in, costly per-seat for an open-source-leaning project; we keep them as future "easy mode" backends behind the OTel collector.
- **Jaeger instead of Tempo** — comparable feature set; we pick Tempo only because the rest of the stack is Grafana-native.
- **ELK for logs** — heavier, not Grafana-native; rejected.
- **Roll our own log/trace store on Postgres** — viable for cost, terrible for ops; rejected.

## References

- PRD §14.4 (Observability)
- Story 0.4.1 (Observability skeleton), Story 0.4.2 (Cost & token accounting)
- ADR-0004 (LLM provider abstraction — emits cost spans)
- Phase 4 Epic 4.1 (SLOs)
