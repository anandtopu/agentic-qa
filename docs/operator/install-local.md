# Install (local)

Get the API + worker stack running on your laptop in ≤ 15 minutes.

## Prerequisites

* Docker 24+ + `docker compose` v2
* Python 3.12 + `uv` (`pip install uv` if you don't have it)
* `pnpm` 9+ (for the web shell + GitHub Action build)
* `make`

## One-time setup

```bash
make install     # uv sync --all-packages + pnpm install
make dev         # docker compose up: postgres + redis + minio + api
```

The API listens on `http://localhost:8080`. Healthcheck:

```bash
curl http://localhost:8080/api/v1/healthz
```

## Apply migrations

The compose file ships migrations as part of the API image's startup
(`alembic upgrade head`). To run them manually against the local
DB:

```bash
make migrate     # (mutates) — alembic upgrade head
```

## Seed a demo workspace

```bash
make seed        # (mutates) — creates a tenant + workspace + sample policy
```

The seed script prints the `workspace_id` + a bearer token to
stdout — use them with the [user guide](../user/getting-started.md).

## Run the test suite

```bash
make test        # all unit + integration (needs the dev stack running)
make test-unit   # unit only — fastest
make test-int    # integration — exercises real Postgres + Redis
```

## Tear down

```bash
make down        # docker compose down (keeps volumes)
make clean       # (mutates) — also drops volumes; you'll re-seed next time
```

## What's running

```text
$ docker compose ps
NAME                  STATE   PORTS
aqao-api           Up      0.0.0.0:8080->8080/tcp
aqao-postgres      Up      0.0.0.0:5432->5432/tcp
aqao-redis         Up      0.0.0.0:6379->6379/tcp
aqao-minio         Up      0.0.0.0:9000->9000/tcp
```

`minio` stands in for S3 evidence; the API is configured to point
at it via `AQAO_EVIDENCE_BUCKET_URL`.

## Next

→ [Install (cloud)](install-cloud.md) when you're ready for staging.
