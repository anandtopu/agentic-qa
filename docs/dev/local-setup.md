# Local setup

Goal: a new contributor can hit `/healthz` in under 30 minutes on a clean machine.

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12 | `pyenv install 3.12` or system package |
| uv | latest | `pipx install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh` |
| Node | 20 LTS | `nvm install 20` |
| pnpm | latest | `corepack enable && corepack prepare pnpm@latest --activate` |
| Docker | 24+ | docker.com |
| Make | any | macOS/Linux native; Windows: use Git Bash or WSL2 |

## First run

```bash
cp .env.example .env
make install      # uv sync + pnpm install
make hooks        # install pre-commit
make dev          # docker compose up (Postgres, Redis, MinIO, API)
curl http://localhost:8000/healthz
```

## Daily loop

```bash
make api           # run API outside docker, with reload
make test-unit     # fast feedback
make lint format   # before pushing
```

## Troubleshooting

- **Port conflicts:** override `QAFORGE_API_PORT` in `.env` or stop the conflicting process.
- **Postgres won't start:** `docker volume rm qaforge_pgdata` and retry.
- **`uv sync` fails on Windows:** use the `uv` Windows installer (not pipx); ensure `LongPathsEnabled` is on.
- **Pre-commit complains about line endings:** run `git config core.autocrlf input` once.

## IDE

- **VS Code:** install Python, Pylance, Ruff, ESLint, Prettier, EditorConfig extensions. Open the workspace at the repo root.
- **PyCharm:** mark `apps/api/src` and each `packages/*/src` as Sources Root.
