# Database migrations

Migrations are managed by **Alembic 1.13+** and live under
`apps/api/migrations/versions/`. The database URL is resolved at runtime
from `AQAO_DATABASE_URL` via `aqao_api.config` — never hard-coded
in `alembic.ini`.

## Running migrations

```bash
make migrate                                # upgrade head against $AQAO_DATABASE_URL
uv run alembic -c apps/api/alembic.ini current
uv run alembic -c apps/api/alembic.ini history --verbose
uv run alembic -c apps/api/alembic.ini -x url=postgresql+psycopg://...  upgrade head  # ad-hoc URL
```

## Authoring a new migration

```bash
uv run alembic -c apps/api/alembic.ini revision --autogenerate -m "add workspaces table"
```

Then:

1. Open the generated file under `apps/api/migrations/versions/`.
2. Review every operation — autogenerate is best-effort, not authoritative.
3. Implement `downgrade()` if at all possible.
4. Commit alongside the model change.

## Conventions

- **Forward-only is the default.** Implement `downgrade()` for everything
  reversible (column adds, index changes, reversible data backfills).
  When `downgrade` is genuinely impossible (irreversible data transform),
  raise `NotImplementedError` with a one-line reason.
- **Naming:** the constraint naming convention is set on
  `aqao_api.db.base.NAMING_CONVENTION`. Do not deviate — Alembic
  reversibility depends on it.
- **Tenancy column:** every tenant-scoped table carries
  `tenant_id UUID NOT NULL REFERENCES tenants(id)`. Place `tenant_id` as
  the first column after the primary key. Always add a composite index
  `(tenant_id, <natural lookup key>)`.
- **Timestamps:** every row has `created_at` and `updated_at`
  (`TIMESTAMPTZ NOT NULL DEFAULT now()`). Updated-at is maintained by a
  Postgres trigger added in the row-level-security migration.
- **RLS policies:** for every new tenant-scoped table the migration
  must also `ENABLE ROW LEVEL SECURITY` and create a `USING
  (tenant_id = current_setting('app.current_tenant_id')::uuid)`
  policy (ADR-0007).
- **Append-only tables** (`audit_events`, `usage_records`): no
  UPDATE/DELETE policies on the application role.

## CI

`make migrate` runs against an ephemeral Postgres in CI; the build fails
if `alembic upgrade head` fails or if `--check` detects a drift between
ORM metadata and the head revision.
