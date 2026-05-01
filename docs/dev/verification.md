# Local verification checklist

A consolidated list of commands to run when verifying work before a commit
or after a long agent-driven session. Order matters: cheap-and-fast
checks first, integration last.

## 1. Static checks (no DB, no Docker)

```bash
# Python
uv sync --all-packages
uv run ruff check .
uv run ruff format --check .
uv run mypy -p aqao_api -p aqao_agents -p aqao_eval -p aqao_redaction -p aqao_tools

# Web
pnpm install
pnpm --filter aqao-web typecheck
pnpm --filter aqao-web lint
pnpm --filter aqao-web build
```

Expected: every command exits 0.

## 2. Unit tests (no DB)

```bash
uv run pytest -m "not integration" --no-cov
```

Expected: all tests pass; the `integration`-marked suite is deselected.

## 3. Integration tests (Postgres required)

Requires Docker Desktop running.

```bash
make dev                              # Postgres + Redis + MinIO + API + Web
make migrate                          # alembic upgrade head against fresh DB
AQAO_DATABASE_URL=postgresql+psycopg://aqao:aqao@localhost:5432/aqao \
  uv run pytest -m integration --no-cov
make down
```

What this exercises that unit tests can't:

- `alembic upgrade head` + `downgrade base` round-trip (Story 0.2.3).
- RLS isolation: cross-tenant reads return 404, never 403/200 (Story 1.1.1 + future Story 3.1.1).
- JSONB column round-trip on `workspaces.environments` and `audit_events.payload`.
- `workspaces` unique `(tenant_id, name)` constraint mapping to `DuplicateResourceError`.
- `updated_at` trigger firing on UPDATE.
- API HTTP round-trip with header-based tenant scoping.

## 4. Web smoke (manual, requires Docker)

```bash
make dev
# Visit:
# - http://localhost:3000           — homepage
# - http://localhost:3000/api/healthz — Next.js health
# - http://localhost:8000/healthz   — API health
# - http://localhost:8000/docs      — FastAPI Swagger
```

## 5. End-to-end verification (post-Phase-1)

When Phase 1 is feature-complete, run the demo scenario from PRD §21
five consecutive times against the sample e-commerce app:

```bash
make e2e        # Phase 1 exit checklist target (does not exist yet)
```

## 6. Full belt-and-braces

```bash
make lint
make format
make typecheck
make test
make eval       # Phase 2+ — eval harness is wired but datasets land later
```

## When something fails

- **`alembic upgrade head` complains about RLS / role**: confirm the
  Postgres user can `ALTER TABLE` and `CREATE POLICY`. The dev compose
  uses a superuser-equivalent.
- **mypy "Source file found twice"**: `rm -rf .mypy_cache` and re-run.
- **pytest collection "No module named 'tests.foo'"**: a stray
  `__init__.py` was added under `*/tests/` — delete it. We rely on
  pytest rootdir-based discovery.
- **Integration suite skipped**: `AQAO_DATABASE_URL` not set, or
  Postgres unreachable.
- **Web build fails on `unrs-resolver` postinstall**: re-run
  `pnpm install` once; native binary fetch is occasionally flaky.

## Known deferred verifications (not yet runnable)

| Verification | Blocked by |
|---|---|
| `pnpm build` of `apps/web` Docker image | Docker daemon not running on dev box |
| `make eval` real run | Eval datasets land in Phase 2 Epic 2.6 |
| End-to-end demo (PRD §21) | Sample app + remaining Phase 1 stories |
| Helm release in `deploy-staging.yml` | `infra/helm/aqao` lands in Phase 3 Story 3.6.2 |
| External pen-test | Phase 4 Epic 4.4 |
