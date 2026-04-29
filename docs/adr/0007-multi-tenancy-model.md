# ADR-0007: Multi-tenancy — row-level with Postgres RLS

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Tech lead
- **Consulted:** Security, SRE
- **Informed:** All eng

## Context

PRD §11.1 + Epic 3.1 require multi-tenant isolation. Tenants ("organisations" in product terms) own one or more workspaces; cross-tenant access must be impossible (Story 3.1.1: cross-tenant attempts return 404, not 403, and alert). The choice of tenancy model is foundational — changing it after Phase 1 is invasive.

The candidates are: schema-per-tenant, database-per-tenant, and row-level (shared schema with `tenant_id` columns). Trade-offs:

| Approach | Isolation | Ops cost | Migration cost | Fit for Phase 1 |
|---|---|---|---|---|
| DB-per-tenant | Strongest | Highest (N DBs) | Highest | Poor |
| Schema-per-tenant | Strong | High | High | Poor |
| Row-level | App-enforced + RLS | Lowest | Lowest | Good |

We have many small tenants (eventually) and shared agent/eval infrastructure. The PRD's success metrics don't require physical isolation; they require provable logical isolation.

## Decision

**Row-level multi-tenancy with PostgreSQL Row-Level Security (RLS) policies as the second line of defence.**

Concretely:

- Every tenant-scoped table has `tenant_id UUID NOT NULL` with an FK to `tenants.id` and an index `(tenant_id, created_at DESC)` (or the natural lookup key prepended).
- Application sets a per-request session variable: `SET LOCAL app.current_tenant_id = '<uuid>';` from the validated JWT, in a single FastAPI dependency that owns the DB session.
- Every tenant-scoped table has an `RLS` policy `USING (tenant_id = current_setting('app.current_tenant_id')::uuid)`. A connection without the variable set sees nothing.
- Two DB roles: `qaforge_app` (RLS enforced; the API uses this) and `qaforge_migrate` (RLS bypassed; only Alembic uses this).
- `tenants` itself, `users`, and a small set of platform tables are exempt from RLS and accessed only via privileged queries.
- Every test in Story 3.1.1 attempts cross-tenant reads/writes and asserts they fail.

Migration to schema-per-tenant remains technically possible later (the schema is row-level-friendly), but the bar to break this decision is "we have a customer who contractually requires physical isolation" — an explicit ADR-supersession event.

## Consequences

- **Positive:** lowest ops cost; one schema to migrate; agent/eval/cost-tracking infrastructure remains shared; RLS provides defence-in-depth even if an application bug forgets the `WHERE tenant_id = …` clause.
- **Negative:** RLS adds query-planner complexity and can make some queries 10–20% slower; we mitigate with the leading-column index and by running EXPLAIN diffs in CI for hot paths. Forgetting `SET LOCAL` in a new code path silently returns empty results — we add a contract test that asserts every API endpoint touches the dependency that sets it.
- **Neutral:** team must learn Postgres RLS semantics and the `current_setting` pattern; we accept this as a one-time learning cost.

## Alternatives considered

- **Schema-per-tenant** — strong isolation but Alembic across N schemas is painful, connection-pool sharing is awkward, and shared cross-tenant analytics get harder.
- **Database-per-tenant** — strongest isolation but unrealistic ops cost for early-stage SaaS; revisit if/when a regulated customer requires it.
- **Application-only isolation (no RLS)** — every query depends on a developer remembering `WHERE tenant_id = …`; one mistake leaks data. PRD §14.2 + Story 3.1.1 effectively rule this out.

## References

- PRD §11.1, §14.2 (Security)
- Epic 3.1 (Multi-tenant RBAC), Story 3.1.1
- ADR-0008 (Secrets — per-tenant key references)
- `docs/architecture/erd.md`
