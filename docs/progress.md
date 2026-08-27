# Progress

Milestone-by-milestone progress for health-tracker. **Update this file at the
end of every milestone** (see the Definition of done in `AGENTS.md`): record
what landed, the key decisions, and the gate results, then move the milestone
to Done in the overview.

## Overview

| Milestone | Scope | Status | Completed |
|---|---|---|---|
| M0 | Research + plan, AGENTS.md | Done | 2026-08-23 |
| M1 | Scaffold: compose, api/web shells, initial migration | Done | 2026-08-23 |
| M2 | Auth API: register/login/me/profile, JWT + argon2 | Done | 2026-08-24 |
| M3 | Import core: schema, GPX/TCX/FIT parsers, import + activity APIs | Done | 2026-08-24 |
| M4 | Web frontend: feed, upload, activity detail (map/splits/HR), sport views | Done | 2026-08-24 |
| M5 | Docker packaging + user docs (installation, usage, api, data-model) | Done | 2026-08-24 |
| M6 | Hardening: limits, backup story, CI, release | Done | 2026-08-25 |
| M7 | Reference table: sport types (`activity_types` + FK) | Done | 2026-08-25 |
| M8 | Reference tables: `source_formats` + `split_units` | Done | 2026-08-25 |
| M9 | Identifier convention: int `id` PK + public `uuid` column | Done | 2026-08-26 |
| M10a | Provider foundation: `providers` + `provider_accounts`, adapter contract, shared `import_parsed` | Done | 2026-08-26 |
| M10b | Strava adapter: OAuth2 + v3 API client, JSON → ParsedActivity conversion | Done | 2026-08-26 |

> 2026-08-25 — First release: **v0.2.0** tagged (see `CHANGELOG.md`); the
> deployed stack reports it at `GET /api/v1/health`.

> 2026-08-25 — Refactor + compliance batch (pre-M6): removed all third-party
> brand references, introduced a unit-of-work + dependency-injection +
> standardized-logging pattern for the API, and completed the dependency
> license audit (no AGPL / strong copyleft). See the entry below.

## M10b — Strava adapter: OAuth 2.0 + v3 API client, conversion (2026-08-26)

The first provider adapter, built strictly against the M10a contract — no
routes, no UI, no config wiring yet (those are M10c–M10d). Strava is a
reference implementation: a later provider (Garmin, Polar, ...) is a new
`providers/<name>/` subpackage, not core changes.

**Gates:** `make lint` green (ruff, mypy, tsc, eslint) · `make test` green
(131 tests: 94 pre-existing + 37 new Strava tests) · api image rebuilt and
smoke passed · adapter verified importable in the running container.

- New `app/providers/strava/` package:
  - `StravaClient` — thin synchronous `httpx` client for the v3 endpoints
    (`/oauth/token`, `/oauth/revoke`, `/athlete`, `/athlete/activities`,
    `/activities/{id}`). Transport only: no domain logic. Maps 401 →
    "re-authorize" error, 429 → `ProviderUpstreamError` carrying
    `retry_after_seconds` (from `Retry-After`), other 4xx/5xx → error with
    the provider's `detail`/`message`, and network failures / non-JSON
    bodies → `ProviderUpstreamError`. Tokens travel in headers/form fields
    only — never in URLs, logs, or exceptions.
  - `StravaAdapter` — implements `ProviderAdapter`: builds the authorize URL
    (client_id, redirect_uri, scope, response_type=code, state), maps the
    `/oauth/token` response to `ProviderCredentials` (validates required
    fields, unix `expires_at` → UTC datetime, athlete → external id +
    display name), refresh (the refresh token **rotates** — the latest is
    returned), identity, paged activity ids, and full-activity conversion.
  - `convert.py` — pure Strava JSON → `ParsedActivity`. Null-safe; missing
    fields stay `None`. Summary HR/cadence double as fallbacks when
    trackpoints carry no samples; 0 distance/calories/elevation → `None`;
    trackpoint `time` (a seconds offset from start) → absolute UTC;
    negative longitudes preserved.
- Sport mapping (Strava `sport_type` → `activity_types.value`): 27 Strava
  types mapped (Running/TrailRun/VirtualRun/Canicross → running; Cycling and
  variants → cycling; Rowing → rowing; Yoga/Pilates → yoga; Strength/Gym/
  WeightLifting/Crossfit/Kickboxing/MartialArts → strength; Swim/
  OpenWaterSwim → swimming; Walking → walking; Hike/Hiking → hiking).
  Anything unmapped → `other` with a warning.
- `ProviderUpstreamError` gained `retry_after_seconds` so the M10d sync loop
  can back off on rate limits instead of hammering Strava.
- `httpx` promoted from a dev dependency to a runtime dependency (providers
  make outbound HTTPS calls).
- `ActivityStatistics` now falls back to `ParsedActivity.cadence_avg_rpm`
  when trackpoints carry no cadence samples (mirroring the existing HR
  fallback). No-op for file imports (parsers never set it); pins the
  contract the provider path relies on.
- Cursor semantics: the opaque `sync_cursor` is the unix start-timestamp of
  the page's oldest activity; a full (100) page advances it, a short/empty
  page ends the walk. Re-fetching the boundary activity (if Strava treats
  `after` as inclusive) is harmless — the dedup index imports each
  `(provider, external_activity_id)` once.
- Tests (37): `test_strava_client.py` (request construction — endpoints,
  bearer/basic auth, after-cursor param, secrets-not-in-URL — and failure
  mapping: 401/429±Retry-After/400-detail/503/transport/non-JSON) via
  `httpx.MockTransport`; `test_strava_adapter.py` (authorize URL params,
  code exchange + field validation, refresh rotation, identity, revoke,
  id-page cursor advance/stop, and fixture-driven conversion for running /
  rowing / strength / unknown-sport / opt-out-HR / minimal / malformed
  trackpoints); `test_activity_stats.py` (summary-fallback contract).

## M10a — Provider foundation: schema, adapter contract, shared import path (2026-08-26)

First step of the M10 Strava integration, built **provider-agnostic** so
later providers (Garmin, Polar, ...) are adapters, not rewrites. This
milestone lands the data model, the code-side contracts, and the shared
persistence path — with **no Strava-specific code, no routes, and no UI**
yet (those are M10b–M10d).

**Gates:** `make lint` green (ruff, mypy, tsc, eslint) · `make test` green
(94 tests: 78 pre-existing + 16 new provider tests) · migration verified
up/down/up on a fresh database · live stack migrated in place, rebuilt,
smoke passed · pre-existing rows verified intact.

- Migration `20260826000001_providers.sql`: new `providers` reference table
  (seeded `strava`) and `provider_accounts` (one of a user's **own**
  connected third-party profiles: external identity, OAuth credentials,
  `token_expires_at`, `scope`, `last_sync_at`, opaque `sync_cursor`;
  `UNIQUE (user_id, provider)`, `user_id` FK → `users (uuid)` ON DELETE
  CASCADE). `activities` gains nullable `provider` (FK → `providers.value`)
  and `external_activity_id`, plus a **partial unique index** on
  `(provider, external_activity_id) WHERE both NOT NULL` so a provider
  activity imports at most once (NULL provenance never collides).
  `activities.source_format` becomes nullable — it now describes the
  file/export format only, not "where it came from".
- Provenance model (key decision): where an activity came from is a
  **column, not a table** — `source_format` for files, `provider` +
  `external_activity_id` for fetched rows. Both sources land as ordinary
  `activities` rows through one shared code path.
- New `app/providers/` core: `ProviderAdapter` abstract base (authorize
  URL, code exchange, refresh, identity, paged activity ids, full-activity
  fetch → `ParsedActivity`, revoke) + `ProviderRegistry` (value → adapter)
  + shared dataclasses (`ProviderCredentials`, `ProviderIdentity`,
  `ActivityIdPage`). Adapters are stateless per user and only ever fetch the
  connected user's own activities. `Provider` StrEnum mirrors the seeded
  reference rows (no `Provider` ORM model — reference tables have no models,
  so the FK lives in the migration SQL only, like `sport_type`).
- `ImportService.import_parsed()` extracted as the shared persistence path:
  `import_activity` (file upload) now detects → parses → stores the file →
  calls `import_parsed`; provider sync (M10d) will call `import_parsed`
  directly with `provider`/`external_activity_id`. It validates the
  `provider` against the `Provider` enum before the FK backstop.
- `Activity` model + mapper + `ActivityDetailView.source_format` now
  nullable; web `ActivityDetailView` type widened to `string | null` and the
  detail page hides the "Imported from …" line when there is no file format.
- `ProviderUpstreamError` (502 `PROVIDER_ERROR`) added to the `AppError`
  hierarchy for adapter network/provider failures.
- Tests (`tests/test_providers.py`): seed↔enum match; `ProviderAccountDao`
  add/get/soft-delete/noop/cascade + `UNIQUE (user_id, provider)`; provenance
  stored for both file and provider paths; NULL-provenance rows don't
  collide; duplicate `(provider, external_activity_id)` rejected; unknown
  provider rejected; timestamp-less activity rejected; registry
  register/get/available + unknown + duplicate.
- Docs: `AGENTS.md` (Provider rules, layout, project scope), `data-model.md`
  (tables, conventions, relationship overview, migrations), `architecture.md`
  (Providers section, errors, "no cloud by default").

## M9 — Identifier convention: int `id` PK + public `uuid` column (2026-08-26)

Established the project-wide identifier convention: **every non-reference
table has an int `id` primary key, and rows that are publicly identified
additionally carry a `uuid` column the API exposes as the public `"id"`**.
The API contract, URLs, and JWTs are unchanged (they kept speaking uuid);
older code can ignore the int ids. Reference tables (text key) are the only
exception. `strength_exercise_sets` (already int-PK) gained a public `uuid`
as the first future URL-addressable child resource.

**Gates:** `make lint` green (ruff, mypy, tsc, eslint) · `make test` green
(78 tests, including new DAO base-method tests) · migration verified
up/down/up on a fresh database with FK re-pointing checks · live stack
migrated in place, rebuilt, smoke passed · pre-existing rows verified
intact (uuids preserved through the rename; old users' activities still
join).

- Migration `20260825000005_int_ids_and_public_uuids.sql`: `users`/
  `activities` — old PK-uuid column renamed to `uuid` (kept unique), new
  `id bigint GENERATED BY DEFAULT AS IDENTITY` PK. The 1:1 satellites
  (`user_profiles`, `activity_hr_zones`, the four `<sport>_activity`)
  switched from uuid PK to int `id` PK with the uuid FK kept as a unique
  column. Dropping the old PKs required temporarily dropping the incoming
  FKs (10 total) and re-adding them against the uuid columns; down reverses
  the whole dance.
- Models: `app/models/base.py` now defines `IntIdModel` and
  `IntIdUuidModel`; all non-reference models retrofitted; new
  `StrengthExerciseSet` model (int PK + public uuid, no audit columns —
  immutable bulk detail, matching its DDL).
- DAOs: `app/dao/base_dao.py` defines `BaseDao` (session + model injection,
  `list(offset, limit)`), `IntIdDao.get_by_id`, `IntIdUuidDao.get_by_uuid`;
  all DAOs retrofitted; new `StrengthExerciseSetDao` exercises the uuid
  layer.
- Ripple: mappers now map `model.uuid` → view `id`; auth/activities/users
  routes and `get_current_user` use the uuid; JWTs carry the uuid as before.
  Covered by the existing 76 tests (all green) plus 2 new DAO tests.
- Rule codified in `AGENTS.md` (Database rules → Table conventions) and
  documented in `docs/data-model.md` + `docs/architecture.md`.

## M8 — Reference tables: source formats + split units (2026-08-25)

Finished applying the M7 convention to the two remaining enum-like columns,
so the rule now has zero exceptions in the schema.

**Gates:** `make lint` green (ruff, mypy, tsc, eslint) · `make test` green
(76 tests) · migration verified up and down, plus direct FK-violation
checks on both columns · stack rebuilt, smoke passed.

- Migration `20260825000004_source_formats_split_units.sql`: seeds
  `source_formats` (`gpx`, `tcx`, `fit`, `apple_health`) and `split_units`
  (`km`, `mi`); `activities.source_format` and `activity_splits.split_type`
  become FKs (CHECKs dropped; down restores them).
- Code enums: `app/imports/base.py::SourceFormat` (parser `source_format`
  ClassVars now use it) and
  `app/services/activity_stats.py::SplitUnit` (`SplitStats.split_type` and
  `compute_splits` typed against it).
- No new API surface: the API keeps returning the value strings; no ORM
  models/DAOs were added because nothing reads these tables yet (they are
  pure schema constraints — a read path would add them when needed).

## M7 — Reference tables: sport types (2026-08-25)

New convention, retroactively applied to its one existing violation: values
that are enums in code are stored in **reference tables** (PK = the value
itself + `description`), referenced by **foreign key** — never bare
`text` + `CHECK`. The rule is now in `AGENTS.md` (Database rules), so it
binds all future schema work.

**Gates:** `make lint` green (ruff, mypy 72 api files, tsc, eslint) ·
`make test` green (76 tests) · migration verified up **and** down on the
live stack, plus a direct FK-violation check (`INSERT … sport_type='skydiving'`
rejected by `activities_sport_type_fkey`) · stack rebuilt, smoke passed,
`GET /sports` serving the new shape on :9090.

### Convention (AGENTS.md → Database rules)
- Reference-table rule written: value = PK + `description`, FK from storing
  tables, rows seeded and immutable (no `updated_at`/`deleted_at`), new
  values added by migration. Code mirrors the set as a Python `Enum`; the
  service validates (app error envelope) and the FK is the schema backstop.
  The public API keeps the value string, never a row id.
- `docs/data-model.md` conventions + table reference updated to match.

### `activity_types` (the sport types)
- Migration `20260825000003_activity_types.sql` (up/down verified): creates
  and seeds `activity_types` (9 rows: running…other, each with a display
  description), drops `activities_sport_type_check`, adds
  `activities_sport_type_fkey` → `activity_types.value`. Down reverses all of
  it (verified).
- API: `ActivityType` model (no audit mixin — reference rows are immutable),
  `ActivityTypeDao`, `SportService`, and `GET /sports` now serves the table:
  `{"sports": [{"value": "running", "description": "Running"}, …]}`.
- Code enum: `app/imports/sports.py::SportType` (StrEnum) mirrors the seeded
  rows; `SPORT_TYPES` is derived from it, `resolve_sport` returns `SportType`
  (still a `str`, so parser/mapper call sites are unchanged). The enum's doc
  points at the table as the schema-level source of truth.
- Web: `SportsView` typed as `{value, description}[]`; the upload sport
  picker now shows the reference `description` (no more client-side
  capitalization).

### Follow-up
- `activities.source_format` and `activity_splits.split_type` are enum-like
  too; converted with the same pattern in M8.

## M6 — Hardening: limits, backup story, CI, release (2026-08-25)

Hardened the running stack against abuse and resource exhaustion, gave the
deployment a real backup/restore workflow, added CI, and defined the release
process.

**Gates:** `make lint` green (ruff, mypy 69 api files, tsc, eslint) ·
`make test` green (76 tests, +5 new) · stack rebuilt and verified live on
:9090 (health `version`, 413 backstop, 429 + `Retry-After`, smoke script,
backup → restore → smoke round-trip) · `docker compose config` + CI YAML
validated.

### Limits
- **Auth rate limiting** — new `app/security/rate_limiter.py::RateLimiter`
  (in-memory sliding window, per-key, thread-safe, stale-key sweep so state
  stays bounded). Login and register are throttled per client IP via
  side-effect dependencies (`app/http/rate_limit.py`): defaults 10 and 5 per
  minute, configurable (`LOGIN_RATE_LIMIT_PER_MINUTE`,
  `REGISTER_RATE_LIMIT_PER_MINUTE`). Over the limit: 429 `RATE_LIMITED` with
  a `Retry-After` header (new `RateLimitExceededError`; the AppError handler
  sets the header). The limiter is a process-wide singleton on `app.state`
  (same rationale as the engine: state must outlive a request; a reset on
  restart is acceptable on a LAN). Conftest resets it per test.
- **Import resource caps** — `MAX_TRACKPOINTS` (default 100,000): files with
  more trackpoints are rejected 422 `IMPORT_ERROR`. The upload route now
  reads at most `max_upload_mb + 1` byte, so an oversized upload is rejected
  without being buffered in full (new test covers both caps).
- **nginx upload cap synced with the API** — `web/nginx.conf` became
  `nginx.conf.template`, rendered at image build time from the same
  `MAX_UPLOAD_MB` value (compose build-arg). nginx's 413 now returns the
  API's JSON envelope (`UPLOAD_TOO_LARGE`) instead of an HTML page.

### Backup story
- `make backup` — `scripts/backup.sh`: `pg_dump -Fc` (custom format:
  compressed, restorable into an empty or existing DB) + the uploads volume
  as a tarball (pinned `alpine:3.20.3` helper, volume name derived from the
  fixed compose project name), into `backups/<utc-timestamp>/`
  (`BACKUP_DEST` to override). Sources `POSTGRES_*` from `.env`.
- `make restore BACKUP=<dir>` — `scripts/restore.sh`: `pg_restore --clean
  --if-exists --exit-on-error` + uploads extraction into the volume.
  Documented as destructive; stop api/web first. `backups/` is git-ignored.
- Verified end-to-end: backup → stop api/web → restore → `make up` → smoke
  passed. (Caught and fixed a real bug while doing so: the restore script
  passed the host tarball path to `tar` inside the container; the backup dir
  is now mounted read-only.)
- `docs/installation.md` Backups section rewritten around the two commands.

### CI (`.github/workflows/ci.yml`)
Four jobs on push/PR to `main`:
- **lint** — ruff + mypy (api), tsc + eslint (web), and a version-drift check
  (`VERSION` == `api/pyproject.toml` version).
- **test** — starts the compose `db` service (`docker compose up -d --wait
  db`) and runs pytest; the existing conftest bootstrap (test DB + dbmate via
  the pinned migrate service) works unchanged because it shells out to
  `docker compose`.
- **build** — `docker compose build` (catches Dockerfile regressions).
- **e2e** — `make up` + `scripts/e2e-smoke.sh` (new `make smoke` target):
  health + version, login-or-register, GPX import through the nginx proxy,
  feed check.

### Release
- `VERSION` file (single source of truth; CI keeps it in sync with
  `api/pyproject.toml`). `GET /api/v1/health` now reports `"version"` (read
  from package metadata, `app/version.py`), so a deployment shows which
  release it runs.
- `CHANGELOG.md` (Keep a Changelog format; 0.1.0 baseline + Unreleased).
- `docs/release.md` — semver rules, cut-a-release steps (tag `vX.Y.Z`),
  update and rollback instructions (with the migration-only-moves-forward
  caveat). README doc index updated.

## Refactor + compliance batch (2026-08-25)

A focused hardening pass on the API and the project framing, ahead of M6.

**Gates:** `make lint` green (ruff, mypy 66 api files, tsc, eslint) ·
`make test` green (71 tests) · API image rebuilt and verified on :9090
(health ok, standardized log lines emitted, demo data removed).

### Reframing (no third-party brand)
- Removed every "Strava" reference from `AGENTS.md`, `README.md`, `docs/`, and
  `web/src/index.css`. The project is now described as a **local-first
  health/fitness aggregation platform where the data is yours**. (The only
  remaining match is a sport-name constant inside the third-party `fitdecode`
  library, which is not ours.)

### API: dependency injection, unit of work, logging
- **Unit of work** — new `app/db/unit_of_work.py::UnitOfWork` wraps the
  request session and owns `commit()`/`rollback()`/`close()`. The per-request
  dependency is now `get_unit_of_work` (was `get_db_session`). Services commit
  through the UoW (`self._unit_of_work.commit()`) instead of reaching into
  `dao.session.commit()`. This makes a multi-DAO operation (an import writes
  the activity + trackpoints + splits + sport row) a single atomic transaction.
  DAOs still never commit; the session is the unit of work, the classic ORM
  pattern — committing inside each DAO would break cross-DAO atomicity.
- **Dependency injection** — `Settings` is a FastAPI dependency
  (`Depends(get_settings)`). `ImportService` now receives `Settings` through
  its constructor instead of calling `get_settings()` directly, so no service
  reaches for a module-level global. The engine remains the one intentional
  process-wide singleton (the connection pool must outlive a request).
- **Logging** — new `app/logging_config.py::configure_logging()` gives the
  `app` logger one consistent handler/format (without touching uvicorn's
  loggers); called from `create_app()`. Every logging module uses
  `logging.getLogger(__name__)`; added loggers to the auth/user/activity
  services with meaningful events.
- **Tests** — `conftest.py` overrides `get_unit_of_work`, and the
  `uploads_dir` fixture overrides the `get_settings` dependency (no more
  module monkeypatching).

### License audit
Verified every installed Python and JS dependency's license:
- **No AGPL and no strong copyleft (GPL) in the dependency tree** (scanned all
  installed `dist-info` metadata and all `node_modules` package manifests).
- Python: all permissive (MIT / BSD-3 / Apache-2.0 / MIT-0 / ISC / MPL-2.0 /
  Unlicense) **except `psycopg` (LGPL-3.0-only)** — a *weak* copyleft, used as a
  dynamically-loaded driver, so it does not copyleft our code and is not
  network-copyleft.
- JS: all permissive **except `react-leaflet` (Hippocratic-2.1)** — a
  permissive license with an added "non-malicious use" clause (not copyleft,
  not AGPL); safe for our use. `leaflet` is BSD-2-Clause.
- **No logic copied from non-public projects.** The TCX parser is original code
  over the public TCX format spec; `gpxpy`/`fitdecode` are imported as licensed
  libraries. The only reused artifacts are fitdecode's MIT-licensed `.fit` test
  fixture files (test data, attributed).

## M5 — Docker packaging + user docs (2026-08-24)

Made the deployment production-ready per the packaging gate and wrote the
full user documentation set.

**Gates:** `make lint` green · `make test` green (71 tests) · API image
rebuilt multi-stage and re-verified on :9090 (health, non-root `appuser`,
code from venv, uploads writable, pinned dbmate applies migrations).

### Docker packaging
- **API Dockerfile is now multi-stage** (was single-stage): a build stage
  installs the app + dependencies into a virtualenv (`python -m venv` +
  `pip install .`); the runtime stage copies only the virtualenv. This matches
  the AGENTS.md gate ("Docker images: multi-stage, pinned base images,
  non-root user for the API") and keeps the runtime image small (~76 MB).
- **dbmate pinned** from `:latest` to `2.35.0` in `docker-compose.yml` (the
  version the migrations were developed and tested against).
- Verified: API runs as `appuser` (uid 1000), imports `app` from
  `/opt/venv/.../site-packages`, `/data/uploads` is writable, and the pinned
  `migrate` service reports `Applied: 2, Pending: 0`.
- Web image was already multi-stage (build + nginx runtime) and unchanged.

### Documentation (`docs/`)
Six documents, all grounded in the actual code/schema:
- **installation.md** — Docker quick start, `.env` reference table, ports,
  migrations, backups (pg_dump + volumes), production/TLS notes, troubleshooting.
- **usage.md** — end-user walkthrough: account, import, feed, detail,
  heart-rate zones (with the 5-zone table), profile, managing activities.
- **api.md** — REST reference: auth, error envelope + code table, and every
  endpoint (health, auth, users, activities, sports) with request/response
  examples and the exact validation bounds.
- **data-model.md** — conventions (audit, soft delete, uuid vs bigint,
  user scoping) plus a per-table column reference and the migration list.
- **architecture.md** — component diagram, the `http → services → dao →
  models` layering, parser/pure-rule, error model, frontend structure, and the
  key cross-cutting decisions.
- **import-formats.md** — GPX/TCX/FIT specifics, the `0 → null` sentinel rule,
  and the full vendor-label → sport mapping table.
- `README.md` updated: status bumped to MVP and a documentation index added.

## M4 — Web frontend (2026-08-24)

Full React SPA: sign in/up, day-grouped activity feed, drag-and-drop import,
rich activity detail (route map, splits, heart-rate chart + zones, sport
metrics), and a profile page with HR-zone settings.

**Gates:** `tsc --noEmit` clean · `eslint` clean · `vite build` succeeds ·
web image rebuilt and smoke-tested on :9090 (SPA + assets + SPA fallback +
API proxy) · live authenticated round-trip through :9090
(register → profile PATCH → GPX import 201 → list/detail/trackpoints → delete
204, demo data removed). Manual browser click-through is the remaining manual
check.

### Dependencies
`react-router-dom` 7, `@tanstack/react-query` 5, `leaflet` + `react-leaflet` 5,
`recharts` 3, `react-dropzone` 20, Tailwind CSS 4 (`@tailwindcss/vite` plugin,
theme tokens in `index.css`).

### Architecture
- `src/api/` — `client.ts` (fetch wrapper, bearer token, `ApiError` with the
  backend error envelope), `types.ts` (mirror of the view schemas), `hooks.ts`
  (all queries/mutations, incl. `useActivitiesInfinite` for load-more).
  Components never call `fetch` directly.
- `src/auth/` — `storage.ts` (localStorage token/user), `AuthContext.tsx`
  (session state + login/register/logout).
- Routes: `/login`, `/register` (`PublicOnly` — signed-in users are bounced to
  `/`) and the protected app shell (`ProtectedRoute` → `Layout` with nav +
  sign-out): `/` feed, `/upload`, `/activities/:id`, `/profile`.
- Design: neutral stone palette + a single calm teal accent (`#2f6f6a`);
  plain Tailwind utility classes.

### Pages
- **Feed** — day-grouped (local date of `started_at`, "Today"/"Yesterday"
  labels), newest first, 20 per page with "Load more"
  (`useInfiniteQuery`); empty state links to upload.
- **Upload** — `react-dropzone` (.gpx/.tcx/.fit, rejects others by name),
  optional sport override (from `GET /sports`, default "detect from file") and
  title override; on 201 navigates straight to the new activity.
- **Detail** — stat grid (distance/time/moving/elevation/calories/pace/HR/
  cadence), Leaflet route map (OSM tiles, only when GPS present), km + mi
  split tables (per-split HR/cadence columns appear only when data exists),
  heart-rate line chart + 5-zone bar chart (recharts), sport-specific metric
  cards dispatched by `sport_type` (`features/SportDetails.tsx`: running /
  cycling / rowing / strength + generic fallback), inline rename (PATCH),
  delete with confirm (204 → back to feed), source format + original filename.
- **Profile** — account info, max/resting HR settings (feeds the backend's
  zone computation), password change.
- **Auth** — login/register cards with inline error display from the API
  error envelope.

## M3 — Import core (2026-08-24)

End-to-end activity import: upload a GPX/TCX/FIT file, get a fully derived
activity (splits, HR zones, sport metrics) back through the API.

**Gates:** `make lint` green · `make test` green (71 tests) · E2E verified
through the Docker stack on :9090 (all three formats, then demo data removed).

### M3a — Activities schema
- Migration `db/migrations/20260823000002_activities.sql` (up/down verified):
  - `activities` — common metrics, uuid PK, user-scoped, soft delete
  - `activity_trackpoints` — bulk immutable samples (no audit columns by design)
  - `activity_splits` — precomputed per-km and per-mile splits
  - `activity_hr_zones` — 1:1 seconds in five percent-of-max-HR zones
  - `running_activity`, `cycling_activity`, `rowing_activity`,
    `strength_activity` — 1:1 sport-specific metrics
  - `strength_exercise_sets` — per-set detail (populated later by manual
    strength entry, not by file import)

### M3b — Parsers (`api/app/imports/`)
- Pure `bytes -> ParsedActivity`, one class per format behind the
  `ActivityParser` ABC; `FormatDetector` tries FIT magic bytes first, then
  extension; unknown format raises `ActivityImportError` (422 `IMPORT_ERROR`).
- **GPX** (gpxpy): vendor-namespace-agnostic extension reading
  (hr/cadence/power/speed), name from `<metadata>` or `<trk><name>`, sport
  from `<trk><type>`.
- **TCX** (in-repo ElementTree parser): namespace-free local-name lookups,
  per-lap distance/moving-time accumulation, power from `<Extensions>`.
- **FIT** (fitdecode 0.11 iterator API): strict CRC, raw int positions
  (×1e-7 degrees per the FIT spec), session stats (sport, distance, calories,
  ascent, HR, power).
- Shared helpers: haversine distance, elevation gain, ISO-8601 time/duration
  parsing; `resolve_sport()` folds vendor labels ("Run Mode", "Indoor Rower"…)
  into the canonical sport set.
- Fixtures in `api/tests/fixtures/`: scripted `run_sample.gpx` and
  `cycle_sample.tcx`; real Garmin files from fitdecode's MIT-licensed test
  data (`run_garmin_fenix5.fit`, `cycle_garmin_fenix5.fit`, plus corrupt-CRC
  and truncated files for error paths).
- Note: `cadence/power/hr = 0` is normalized to `None` in all parsers — 0 is
  a "no data" sentinel and the columns are constrained `> 0`.

### M3c — Persistence and statistics
- 8 ORM models; one DAO per table. The four sport tables share
  `SportActivityDao[ModelT]` (generic bound to `SportActivityMixin`) with four
  thin concrete DAOs.
- `ActivityStatistics` (pure, no DB): km/mi splits with per-split HR/cadence,
  five-zone HR distribution, per-sport pace/power/500 m split. File-provided
  summaries win; trackpoints fill gaps (HR min/avg/max, cadence avg, power).
- `ImportService`: size check → detect → parse → validate (timestamps
  required) → resolve sport (override > file hint > default `running`) and
  name (override > file > filename stem) → store the original file at
  `/data/uploads/<user_id>/<activity_id>.<ext>` → insert activity +
  trackpoints + splits + zones + sport row in one commit.
- `ActivityService`: user-scoped list (newest first, paginated) / detail /
  trackpoints / splits, update (name/description/sport), soft delete. Other
  users' activities are 404, not 403.
- HR zones use the user's profile max HR when set, otherwise the activity's
  own max HR. Last partial split is kept only when ≥ 10 % of the unit.

### M3d — Activity API
All routes bearer-authenticated under `/api/v1`:

| Route | Purpose |
|---|---|
| `POST /activities` | multipart upload (`file`, optional `sport_type`, `name`) → 201 detail |
| `GET /activities` | paginated feed (`limit` ≤ 100, `offset`), newest first |
| `GET /activities/{id}` | full detail incl. splits, HR zones, sport metrics |
| `GET /activities/{id}/trackpoints` | all samples in recorded order |
| `GET /activities/{id}/splits` | precomputed splits |
| `PATCH /activities/{id}` | update name/description/sport_type |
| `DELETE /activities/{id}` | soft delete → 204 |
| `GET /sports` | canonical sport list for UI pickers |

## M2 — Auth API (2026-08-24)

**Gates:** 20 tests green at completion · mypy/ruff clean · E2E verified on
:9090.

- `errors/` — `AppError` hierarchy + global handlers producing the
  `{"error": {code, message, details}}` envelope.
- `security/` — argon2id password hashing; JWT HS256, 30-day TTL.
- `models/` + `dao/` — `users`, `user_profiles`; email normalized
  (trim + lowercase) and unique; all queries user-scoped.
- `schemas/` + `services/` — `UserMapper`, `AuthService`, `UserService`.
- Routes: `POST /api/v1/auth/register` (201 + token),
  `POST /api/v1/auth/login`, `GET /api/v1/users/me`,
  `PATCH /api/v1/users/me`, `GET/PATCH /api/v1/users/me/profile`.
- Test infra: `tests/conftest.py` auto-creates/migrates the
  `health_tracker_test` database, overrides `get_db_session`, truncates after
  each test (needs the compose stack running).

## M1 — Scaffold (2026-08-23)

**Gates:** health check + SPA verified on :9090 · pytest/mypy/ruff/tsc/eslint
clean.

- `docker-compose.yml` (db / migrate / api / web), `Makefile`, `.env.example`,
  `LICENSE` (MIT), `README.md`, `.gitignore`.
- API skeleton (`main.py`, `config.py`, `db/session.py`,
  `GET /api/v1/health` with live DB check); web shell (Vite + React + TS).
- Migration `20260823000001_initial.sql`: `users`, `user_profiles`,
  `set_updated_at()` trigger used by all audit tables.
- Fixes worth remembering: dbmate URLs need `?sslmode=disable`; nginx needs a
  runtime DNS resolver (`127.0.0.11`) to resolve the `api` upstream.

## M0 — Plan (2026-08-23)

- Field research and full plan; user decisions recorded: MIT license, project
  lives in the `health-tracker/` subdirectory, 30-day JWT expiry, incremental
  milestone work with a pause + summary at the end of each milestone.
- `AGENTS.md` written: architecture/layering rules, parser rules, database
  rules, frontend rules, quality gates, Definition of done.
