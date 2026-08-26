# AGENTS.md — health-tracker

Guidance for AI agents (and humans) working in this repository.

## Project

Open-source, self-hosted activity and health tracker for the homelab — a
**local-first health/fitness aggregation platform where the data is yours**.
Docker-deployable. **No cloud or third-party service dependencies at runtime.**
Users create an account, import activity files (GPX/TCX/FIT, later Apple Health
export), and view activities — routes, splits, heart rate, calories — in a clean
web UI on port 9090.

## Repository layout

```
health-tracker/
  api/               FastAPI backend (Python 3.12)
    app/
      main.py        app factory + router wiring
      config.py      pydantic-settings configuration
      http/          route handlers (thin: validate -> service -> view)
      services/      business logic (no SQLAlchemy, no ORM objects in signatures)
      dao/           ALL SQLAlchemy code; sessions injected via constructor
      models/        SQLAlchemy 2.0 typed ORM models (Base, mixins)
      schemas/       pydantic v2: requests/, views/, mappers/
      imports/       file format parsers (pure: bytes -> ParsedActivity)
      security/      argon2 password hashing, JWT issuing/verifying
      errors/        AppError hierarchy + exception handlers
      db/            engine + session factory
    tests/           pytest: unit + API integration (TestClient)
    tests/fixtures/  sample .gpx/.tcx/.fit files (and malformed ones)
  web/               React SPA (Vite + TypeScript strict)
    src/
      api/           fetch client + TanStack Query hooks (only place that calls fetch)
      auth/          auth context (JWT storage, login/logout)
      pages/         Login, Register, Activities, Upload, ActivityDetail, Profile
      components/    shared UI (ActivityCard, StatGrid, RouteMap, charts, UploadZone)
      features/      sport-specific detail views (RunningDetail, StrengthDetail, ...)
  db/migrations/     dbmate v2 SQL migrations (single file, up + down)
  docs/              progress.md (milestone log), architecture.md, installation.md,
                     usage.md, data-model.md, api.md, import-formats.md
  docker-compose.yml
  Makefile
  .env.example
```

## Commands

```
make install    # uv sync (api) + npm install (web)
make migrate    # docker compose run --rm migrate up
make api        # run FastAPI in dev mode (uvicorn --reload, local postgres or test db)
make web        # run Vite dev server (proxies /api to :8000)
make up         # docker compose up --build (full stack on :9090)
make test       # pytest (api) + tsc/eslint (web)
make lint       # ruff check + ruff format --check + mypy (api) + eslint + tsc (web)
make seed       # create demo user + sample activities
```

If a command is not in the Makefile yet, add it there — never document one-off
invocations in docs instead.

## Backend rules (FastAPI / Python 3.12)

- **Layering is strict**: `http (routes) -> services (business logic) -> dao (SQLAlchemy) -> models (ORM)`.
  - Route handlers stay thin: parse/validate input, call one service method, return a view.
  - Services contain business logic and never import SQLAlchemy directly.
  - **All SQLAlchemy code lives in DAOs.** Sessions are passed into DAO constructors;
    DAOs never create sessions.
- **Mappers are mandatory.** Each entity has a mapper class with explicit methods:
  `from_request(...) -> Model`, `to_view(Model) -> View`. Routes never construct ORM
  objects and **never return ORM objects** — only pydantic views.
- **Object-oriented, explicit, readable.** Prefer classes with clear responsibilities
  and boring control flow over pythonic idioms (heavy comprehensions, one-liners,
  metaclasses, dunder proliferation). A developer from another language must be able
  to read it.
- **Type hints everywhere.** `mypy --strict` must pass. No `Any` without a comment.
- **Errors**: raise `AppError` subclasses (e.g. `ValidationError`, `NotFoundError`,
  `ImportError_`, `AuthError`). Global exception handlers convert them to a
  structured JSON envelope:
  `{"error": {"code": "...", "message": "...", "details": [...]}}`.
- **No migrations, no schema DDL, no `create_all`** in API code. The API never alters
  the schema; dbmate owns it.
- Configuration via `pydantic-settings` from environment (see `.env.example`).
- All timestamps stored as UTC `timestamptz`; API returns ISO 8601 UTC.

## Parser rules

- `app/imports/` contains one class per format implementing the `ActivityParser`
  abstract base: `parse(bytes) -> ParsedActivity` plus `supports(filename, header)`.
- Parsers are **pure**: input bytes -> `ParsedActivity` dataclass. No DB, no HTTP,
  no global state. All field extraction is null-safe; missing fields stay `None` and
  are recorded in `ParsedActivity.warnings`.
- Library choices: GPX -> `gpxpy`; FIT -> `fitdecode`; TCX -> small in-repo parser
  over stdlib `xml.etree.ElementTree` (no maintained Python TCX library exists).
- Apple Health (zip of encrypted JSON records) is a stretch goal; add
  `apple_health/` parser package when implemented.
- Every parser needs fixture tests, including at least one malformed/corrupt file.

## Database rules (dbmate v2 + Postgres 16)

- Schema changes happen **only** in `db/migrations/*.sql`, applied via dbmate
  (`make migrate` or `docker compose run --rm migrate up`). Never from the API.
- Migration file naming: `YYYYMMDDHHMMSS_description.sql`. Each file contains both
  sections: `-- migrate:up` and `-- migrate:down` (down must actually work).
- Table conventions:
  - `created_at`, `updated_at`, `deleted_at` (`timestamptz`) on every table;
    deletion is soft (`deleted_at IS NOT NULL`).
  - `id bigint` for internal rows; `uuid` (v4) for anything public-facing
    (users, activities and their sub-resources referenced in URLs).
  - Comment every table and every non-obvious column (`COMMENT ON ...`).
  - Prefer standard SQL over Postgres-specific types/features (e.g. `text` +
    `CHECK` constraint instead of `ENUM`; `timestamptz` is fine, it is standard).
  - Timestamps over booleans whenever a "when" matters.
- Email addresses are normalized (trim + lowercase) in the service/mapper layer
  before they reach the DB; `users.email` has a unique constraint.
- Every query that reads user data is scoped by `user_id` (enforced in DAOs).

## Frontend rules (React + TypeScript)

- Vite + React + TypeScript (`strict`), `react-router`, `@tanstack/react-query`,
  Tailwind CSS (neutral stone palette + a single calm accent color),
  `leaflet`/`react-leaflet` with OpenStreetMap tiles, `recharts` for charts.
- All API access goes through `src/api/` (fetch wrapper + query hooks). Components
  never call `fetch` directly.
- One detail view component per sport type under `src/features/`, dispatched from the
  detail page by `sport_type`. A generic fallback view exists for sports without a
  dedicated view.
- Day-based grouping of the activity feed happens in the UI from `started_at`
  (local date), so the feed reads as *Today / Yesterday / …* like a typical
  activity timeline.
- Uploads: `react-dropzone`; multipart `POST /api/v1/activities`.

## Testing and quality gates

- Python: `pytest` for parsers (fixtures), mappers, services, and API endpoints
  (via `TestClient`). `mypy --strict` and `ruff` (lint + format) must pass.
- Frontend: `tsc --noEmit` and `eslint` must pass.
- Never commit `.env`, secrets, or generated upload data. Use `.env.example`.
- Docker images: multi-stage, pinned base images, non-root user for the API.

## Definition of done (per feature)

1. Works end-to-end in `make up` (docker) — not just local dev.
2. Migrations applied cleanly up and down.
3. `make lint && make test` green.
4. Docs updated (`docs/`) where user-visible behavior changed.
5. `docs/progress.md` updated: milestone moved to Done in the overview with a
   dated entry (what landed, key decisions, gate results). Work milestone by
   milestone — pause and summarize at the end of each before starting the next.
