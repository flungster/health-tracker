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
                                                   └──┬───┬─────┘          └──────────┘
                                                      │   └── outbound HTTPS, user-authorized
                                                      │       (connected providers, e.g. Strava)
                                                      ▼ writes original files
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

### Providers

`providers/` is the provider-agnostic half of the third-party integration
layer. A `ProviderAdapter` (abstract base, one concrete adapter per provider
under `providers/<name>/`) turns one external provider into the app's core
concepts: OAuth credentials, the connected user's **own** identity, and their
activities as `ParsedActivity` objects. Adapters are stateless per user —
user-specific state (tokens, sync cursor) lives in `provider_accounts` and is
passed in per call. The core (the `ProviderRegistry`, the provider accounts
DAO, and the shared `ImportService.import_parsed` persistence path) talks to
adapters through this contract only, so adding a provider means adding an
adapter, not new core code. Both import sources (uploaded files and
provider-fetched activities) flow through the same `import_parsed` path and
land as ordinary `activities` rows, distinguished by their provenance
(`source_format` for files, `provider` + `external_activity_id` for fetched).

The first adapter is **Strava** (`providers/strava/`), split into a thin
synchronous `StravaClient` (transport only: builds requests, decodes JSON,
maps 401/429/network failures onto `ProviderUpstreamError`) and the
`StravaAdapter` (domain logic: OAuth code exchange/refresh, identity, paged
activity ids, JSON → `ParsedActivity` conversion). The opaque sync cursor is
the unix start-timestamp of the page's oldest activity, sent as Strava's
`before` parameter so the walk proceeds newest → oldest; re-fetching the
boundary activity is harmless because the dedup index imports each
`(provider, external_activity_id)` once. Conversion is null-safe (missing
fields stay `None`, notable gaps become warnings), summary heart rate/cadence
double as fallbacks when trackpoints carry no samples, and unknown Strava
sport types map to `other` with a warning.

**Connection flow (OAuth).** Adapters are registered at app startup only when
their credentials are present in the environment (`_build_provider_registry`
in `main.py`), so an unconfigured provider reads as 404, not as an error.
`ProviderService` (with `ProviderAccountMapper`) drives the flow:
`GET /providers/{p}/connect` issues a short-lived **signed state token**
(`TokenService.issue_oauth_state`) that binds the flow to the caller, then
returns the adapter's authorize URL. The browser round-trips through the
provider and lands on `GET /providers/{p}/oauth/callback` — a plain browser
redirect that carries **no** `Authorization` header, so the callback
identifies the user through the state token (which also stops forged/crossed
flows). A successful exchange upserts the `provider_accounts` row (reusing the
single `(user, provider)` row, so reconnecting after a disconnect is clean);
the response is a 307 redirect back to the app with `?connected=` /
`?connect_error=`. `disconnect` revokes on the provider (best effort) and
soft-deletes locally. No endpoint ever returns tokens.

**Sync.** `ProviderSyncService` (route `POST /providers/{p}/sync`) pulls a
connection's new activities:

- It ensures a live access token — refreshing through the adapter (and
  persisting the rotated pair) when the cached one is expired — then walks
  the provider's activity list from the stored `sync_cursor`, newest → older,
  one adapter page per call.
- Every page id is checked against the global
  `(provider, external_activity_id)` dedup (an `ActivityDao` existence check
  mirroring the partial unique index); only unseen ids are fetched in full and
  imported through the shared `ImportService.import_parsed` path, so provider
  activities are ordinary `activities` rows with provider provenance.
- The cursor is checkpointed (committed) after each full page. A run that
  finishes the walk clears the cursor; a run that hits the per-run page cap
  (`MAX_SYNC_PAGES`) or a provider failure (rate limit, 5xx) keeps it, so the
  next run resumes where this one stopped. `last_sync_at` is stamped when a
  run completes.
- Rate limits surface as 502 `PROVIDER_ERROR` with a `Retry-After` header (the
  error handler sets it for any `AppError` carrying `retry_after_seconds`).
  Syncs are user-triggered; a scheduled background sync would reuse the same
  service.

### Errors

Services/DAOs raise `AppError` subclasses (`AuthenticationError`,
`NotFoundError`, `ConflictError`, `ValidationError`, `ActivityImportError`,
`ProviderUpstreamError`).
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
  derived once, at import time (file upload or provider sync), and stored.
  Reads are cheap and the UI doesn't recompute. Relabeling an activity's
  sport (PATCH) does not recompute.
- **Reference tables for enum-like values** — value sets that are enums in
  code are seeded reference tables keyed by the value itself
  (`activity_types`, `source_formats`, `split_units`, `providers`), referenced
  by foreign key from the tables that store them; membership is enforced by
  the schema. Code mirrors each set as a Python `Enum` (`SportType`,
  `SourceFormat`, `SplitUnit`, `Provider`) and validates against it before the
  FK does; the API speaks the value string, never a row id.
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
- **No cloud by default** — no telemetry and no required external services;
  everything runs locally and the app is fully functional offline. Fetching
  activities from a connected provider (e.g. Strava) is strictly opt-in: the
  user connects their **own** account via OAuth, the API then makes outbound
  HTTPS calls to that provider on the user's behalf (read-only, their own
  activities), and nothing is ever *pushed* to a third party. The data is the
  user's and stays in their database.
