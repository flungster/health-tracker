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

> 2026-08-25 — Refactor + compliance batch (pre-M6): removed all third-party
> brand references, introduced a unit-of-work + dependency-injection +
> standardized-logging pattern for the API, and completed the dependency
> license audit (no AGPL / strong copyleft). See the entry below.

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
