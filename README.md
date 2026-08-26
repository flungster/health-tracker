# health-tracker

Self-hosted activity and health tracker for the homelab — a local-first
health/fitness aggregation platform where the data is yours, running entirely
on your own hardware.

Create an account, import activity files (GPX, TCX, FIT) from your watch or
phone, and view your activities — routes, splits, heart rate, calories — in a
clean web UI. No cloud services involved.

> Status: **MVP** — accounts, GPX/TCX/FIT import, and a full activity UI. See
> `docs/` for detailed documentation and `AGENTS.md` for architecture rules
> and the milestone plan.

## Built with AI

health-tracker was written almost entirely by AI: a human sets the direction,
and an agentic coding loop writes and verifies the code, tests, migrations,
and documentation. It is deliberately an experiment in how far a fully
**local, open-source model** stack — no cloud inference — can take a real,
working project.

**Current toolchain (2026-08-25):**

| | |
|---|---|
| Agent | [opencode](https://opencode.ai) — interactive agentic CLI |
| Model | Qwen3.8-27B (MLX 6-bit) — open source, running locally on Apple Silicon via [LM Studio](https://lmstudio.ai) |

No commercial models (OpenAI, Anthropic, …) have been used so far. If that
ever changes, it is recorded in the log below rather than noted silently.

### AI development log

Add a row whenever the agent or model changes.

| Date | Work | Agent | Model |
|---|---|---|---|
| 2026-08-23 – 25 | M0–M6: plan, scaffold, auth, import, web UI, Docker, hardening | opencode | local open-source models via LM Studio (per-session model not recorded at the time) |
| 2026-08-25 | M7–M8: reference tables for enum-like values | opencode | Qwen3.8-27B (MLX 6-bit) via LM Studio |

## Documentation

| Doc | What it covers |
|---|---|
| [Installation](docs/installation.md) | Docker setup, configuration, ports, migrations, backups, production notes. |
| [Usage](docs/usage.md) | How to use the app: importing, the feed, activity detail, zones, profile. |
| [API](docs/api.md) | REST reference: auth, users, activities, sports, errors. |
| [Data model](docs/data-model.md) | The database schema and its conventions. |
| [Architecture](docs/architecture.md) | How the components and layers fit together. |
| [Import formats](docs/import-formats.md) | What GPX/TCX/FIT contribute and the cross-format rules. |
| [Releasing](docs/release.md) | Versioning, cutting a release, updating and rolling back. |
| [Changelog](CHANGELOG.md) | What changed in each release. |

## Components

| Component | Tech | Role |
|---|---|---|
| `api/` | Python 3.12, FastAPI, SQLAlchemy 2 | REST API, auth, file import, storage |
| `web/` | React + TypeScript (Vite) | Web UI on port **9090** |
| `db/migrations/` | SQL via [dbmate](https://github.com/amacneil/dbmate) | All schema changes |
| Postgres 16 | — | Database |

## Quick start (Docker)

```
cp .env.example .env        # set a real JWT_SECRET
make up                     # builds and starts db + api + web
```

Then open <http://localhost:9090>.

Migrations run through the dedicated `migrate` service:

```
make migrate                # apply pending migrations
make migrate-down           # roll back the last migration
```

## Local development

```
make install                # uv sync (api) + npm install (web)
make up                     # start db + api + web in docker (or just: docker compose up -d db)
make api                    # FastAPI with reload on :8000
make web                    # Vite dev server on :5173 (proxies /api to :8000)
make test                   # API tests (needs the compose db running)
make lint                   # ruff + mypy (api), eslint + tsc (web)
make backup                 # back up database + uploads to ./backups/<timestamp>/
make restore BACKUP=...     # restore such a backup (destructive)
make smoke                  # end-to-end smoke test against a running stack
```

## License

MIT — see [LICENSE](LICENSE).
