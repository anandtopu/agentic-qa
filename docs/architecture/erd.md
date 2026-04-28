# Entity-Relationship Diagram

Maps PRD §12 entities to a normalised relational schema. All entities
(except `tenants` and `users`) carry a `tenant_id` for row-level
isolation. Timestamps (`created_at`, `updated_at`) are present on every
row but omitted from the diagram for clarity.

```mermaid
erDiagram
  tenants ||--o{ users : has
  tenants ||--o{ workspaces : owns
  workspaces ||--o{ repositories : has
  workspaces ||--o{ environments : has
  workspaces ||--o{ requirements : ingests
  requirements ||--o{ test_plans : produces
  test_plans ||--o{ test_cases : contains
  test_cases ||--o{ test_runs : executes
  test_runs ||--o{ test_results : yields
  test_results ||--o{ tool_invocations : invokes
  test_runs ||--o{ agent_tasks : drives
  test_results ||--o{ failure_classifications : classifies
  failure_classifications ||--o{ defect_recommendations : suggests
  test_runs ||--|| release_risk_scores : scores
  workspaces ||--o{ approval_requests : raises
  test_runs ||--o{ evidence_artifacts : captures
  workspaces ||--o{ evaluation_datasets : owns
  evaluation_datasets ||--o{ evaluation_runs : runs
  evaluation_runs ||--o{ evaluation_scores : scores
  tenants ||--o{ audit_events : records
  tenants ||--o{ usage_records : meters
```

## Notes

- **Idempotency:** `test_runs` carries a unique `(workspace_id, idempotency_key)`.
- **Append-only:** `audit_events` and `usage_records` are insert-only; mutations are forbidden at the DB role level.
- **Content addressing:** `evidence_artifacts` references object-store keys keyed by SHA-256 (PRD §11.2 evidence store).
- **Indexes:**
  - `(tenant_id, workspace_id)` on every tenant-scoped table.
  - `(test_run_id, created_at desc)` for evidence/result fetches.
  - `gin (tags)` on `test_cases` for tag filters.
