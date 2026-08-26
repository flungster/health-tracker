# Architecture

health-tracker is a self-hosted, Docker-deployed web application with no cloud
dependencies. This page describes how the pieces fit together and the rules
that keep the codebase maintainable. The authoritative rules live in
`AGENTS.md`; this is the narrative version.

## Components

```
            ┌────────────┐  static bundle + /api proxy
 browser ──▶│    web     │──────────────────────────────┐
            │ (nginx +   │                              ▼
            │  React SPA)│                        ┌────────────┐   SQL    ┌──────────┐
            └────────────┘                        │    api     │─────────▶│  db      │
                                                  │  (FastAPI) │          │ Postgres │
                                                  └─────┬──────┘          └──────────┘
                                                        │ writes original files
                                                        ▼
                                                 /data/uploads (volume)
```

| Service | Image / tech | Responsibility |
|---|---|---|
| `db` | Postgres 16 | All persistent data. |
| `migrate` | dbmate (pinned) | One-shot schema migrations; runs on startup. |
| `api` | Python 3.12, FastAPI, SQLAlchemy 2 | Auth, import, storage, REST API. |
| `web` | nginx serving a React SPA | UI; proxies `/api/*` to the api service. |

The `web` and `api` images are built by Docker (multi-stage); `db` and
`migrate` are pinned upstream images. The API and web talk over Docker's
internal network; only `web` is published on the host (default port 9090).

## Backend layering

The FastAPI app enforces a strict request path:

```
http (routes)  →  services (business logic)  →  dao (SQLAlchemy)  →  models (ORM)
```

- **`http/`** — thin route handlers. They parse and validate input, call exactly
  one service method, and return a *view*. No ORM, no queries, no business
  rules.
- **`services/`** — business logic. No SQLAlchemy imports; signatures use
  plain data (views / dataclasses), never ORM objects. Services own the
  transaction boundaries (they commit).
- **`dao/`** — *all* SQLAlchemy code. Sessions are injected via the
  constructor; DAOs never create sessions and never commit. Shared bases in
  `base_dao.py` follow the identifier convention: `BaseDao` holds the
  session + model and provides `list(offset, limit)`; `IntIdDao` adds
  `get_by_id`; `IntIdUuidDao` (extends `IntIdDao`) adds `get_by_uuid`.
  Concrete DAOs are thin: scoped/ordered query variants on top.
- **`models/`** — SQLAlchemy 2.0 typed ORM models (`Mapped[...]`).
- **`schemas/`** — pydantic v2, split into `requests/` (inbound), `views/`
  (outbound), and `mappers/` (the bridge).

**Mappers are mandatory.** Each entity has a mapper with explicit
`from_request(...) -> Model` and `to_view(model) -> View` methods. Routes never
construct ORM objects and never return them — only pydantic views.

### Parsers

`imports/` contains one pure parser class per file format behind the
`ActivityParser` abstract base: `parse(bytes) -> ParsedActivity` plus
`supports(filename, header)`. Parsers have no DB, HTTP, or global state —
bytes in, a format-neutral `ParsedActivity` dataclass out. A `FormatDetector`
picks the parser (FIT magic bytes first, then file extension). See
[import-formats.md](import-formats.md).

### Errors

Services/DAOs raise `AppError` subclasses (`AuthenticationError`,
`NotFoundError`, `ConflictError`, `ValidationError`, `ActivityImportError`).
Global handlers convert them to a structured JSON envelope:

```json
{ "error": { "code": "...", "message": "...", "details": [] } }
```

This keeps "expected" failures consistent and makes the API friendly to
non-browser clients.

## Frontend

A Vite + React + TypeScript SPA (`strict`) with:

- **`src/api/`** — the only place that calls `fetch`. A thin `client.ts`
  wrapper (adds the bearer token, normalizes errors into `ApiError`) plus
  TanStack Query hooks in `hooks.ts`. Components never touch `fetch` directly.
- **`src/auth/`** — session state (JWT + user) in React context, persisted to
  `localStorage`.
- **`src/pages/`** — Login, Register, Activities (feed), Upload,
  ActivityDetail, Profile.
- **`src/components/`** — shared UI (cards, stat grid, route map, charts,
  upload zone).
- **`src/features/`** — sport-specific detail panels, dispatched from the
  detail page by `sport_type`, with a generic fallback.

The feed groups activities by local date from `started_at`, so it reads as a
day-grouped timeline (*Today / Yesterday / …*). Maps use Leaflet with
OpenStreetMap tiles — the only outbound request the browser makes.

## Cross-cutting decisions

- **Soft delete everywhere** — nothing is hard-deleted from the database by the
  app; `deleted_at` marks removal and reads filter on it.
- **Precomputed at import** — splits, heart-rate zones, and sport metrics are
  derived once, at import time, and stored. Reads are cheap and the UI doesn't
  recompute. Relabeling an activity's sport (PATCH) does not recompute.
- **Reference tables for enum-like values** — value sets that are enums in
  code are seeded reference tables keyed by the value itself
  (`activity_types`, `source_formats`, `split_units`), referenced by foreign
  key from the tables that store them; membership is enforced by the schema.
  Code mirrors each set as a Python `Enum` (`SportType`, `SourceFormat`,
  `SplitUnit`) and validates against it before the FK does; the API speaks
  the value string, never a row id.
- **Original files kept** — the uploaded file is stored in the `uploads`
  volume at `/data/uploads/<user_id>/<activity_id>.<ext>` for re-import/export.
- **User scoping is a invariant** — every read is scoped by `user_id` in the
  DAOs; foreign rows read as 404.
- **Bounded inputs** — uploads are size-capped (`MAX_UPLOAD_MB`, enforced
  before the full body is buffered), trackpoint-capped (`MAX_TRACKPOINTS`),
  and auth endpoints are rate-limited per client IP (in-memory sliding window,
  429 `RATE_LIMITED` + `Retry-After`). The limiter is a process-wide singleton
  like the database engine: its state must outlive a single request, and a
  reset on restart is acceptable for a LAN deployment.
- **Versioned releases** — the version lives in `VERSION` (mirrored in
  `api/pyproject.toml`, kept in sync by CI) and is reported by
  `GET /health`; releases are git tags, see [Releasing](release.md).
- **No cloud** — no telemetry, no external APIs. Everything runs locally.
