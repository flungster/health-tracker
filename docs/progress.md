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
| M10c | Provider OAuth: connect/disconnect routes + callback, config wiring, profile UI | Done | 2026-08-26 |
| M10d | Provider sync: paged activity walk, dedup, cursor resume, token refresh, sync API + UI | Done | 2026-08-26 |
| M11a | Self-serve provider config: `server_settings` + `provider_credentials` schema, DAOs, Fernet at-rest encryption, `sync_since` floor | Done | 2026-08-28 |
| M11b | Credential resolution: Fernet key bootstrap at startup, registry built from the DB, `STRAVA_*` env vars removed | Done | 2026-08-28 |
| M11c | Client-config API: masked GET, upsert PUT (keep-or-set secret), DELETE, live registry rebuild on write | Done | 2026-08-29 |

> 2026-08-25 — First release: **v0.2.0** tagged (see `CHANGELOG.md`); the
> deployed stack reports it at `GET /api/v1/health`.

> 2026-08-25 — Refactor + compliance batch (pre-M6): removed all third-party
> brand references, introduced a unit-of-work + dependency-injection +
> standardized-logging pattern for the API, and completed the dependency
> license audit (no AGPL / strong copyleft). See the entry below.

## M11c — Client-config API: the deployment's OAuth client, self-served (2026-08-29)

Third slice of M11: the routes that let any signed-in account manage the
deployment's OAuth client for a provider — `GET/PUT/DELETE
/api/v1/providers/{p}/client/config`. What remains: the UI (M11d) and the
sync lookback (M11e).

**Gates:** `make lint` green (ruff, mypy, tsc, eslint) · `make test` green
(191 passed: 178 pre-existing + 13 config-API tests — the M11c contract
stubs went from xfail to real; the only xfail left is the M11e lookback
stub) · api image rebuilt; live smoke passed (below).

### Endpoints (Q11 naming, Q16 edge semantics)
- `GET` → masked view `{provider, configured, client_id, display_name}`.
  `configured` is true only for an active row whose secret decrypts; a row
  with an undecryptable secret reports unconfigured **with the client id
  still visible** so it can be re-saved. Unknown provider → 404.
- `PUT` → 200, the masked view; upsert. `client_id` required (trimmed; empty
  → 422, ≤ 128 chars). `client_secret` required only when nothing usable is
  stored yet (first-time, or re-configuring after a DELETE; empty → 422,
  ≤ 512 chars); omitted/null on an update keeps the stored secret — which
  can never be read back. `display_name`: omitted = keep, null = clear,
  empty string = clear (≤ 100 chars). Unknown provider → 404.
- `DELETE` → 204 soft delete (404 when not configured). User connections are
  untouched: they become orphaned (sync paused; connect/sync 404) until the
  credentials are saved again — re-saving the same app resumes sync with the
  stored tokens.

### Live registry rebuild on write (Q8)
A write calls `swap_registry` (wired in the dependency): after the commit,
the process-wide registry is rebuilt from the database and the displaced
adapters are closed (`close_all`, from M11b). Saving credentials makes the
provider connectable immediately — no restart — verified in the live smoke
below (the connect URL carries the just-saved client id).

### Code shape
`ProviderConfigService` (get/save/remove; explicit validation; encrypts via
the `SecretsBox`; reuses the soft-deleted row so there is one row per
provider) · `ProviderCredentialMapper.to_view(credential, provider,
configured)` (the secret never appears) · `ClientConfigRequest` /
`ClientConfigView` · `ProviderDao.get_by_value` (reference-table check →
404 before any work).

### Tests (13, `tests/test_provider_config_api.py` — contract stubs now real)
Unauthenticated PUT 401 · configure-then-GET masks the secret · PUT without
a secret keeps the existing one · DELETE flips `/providers` to configured
false · unknown provider 404 (GET and PUT) · `configured` flag tracks the
DB · first PUT without a secret 422 · empty client id 422 · oversized field
422 · DELETE without configuration 404 · display_name null clears / omitted
keeps · saved credentials make the provider connectable (write-path
rebuild).

### Live smoke (rebuilt api on :9090)
Fresh user: GET → unconfigured · PUT → 200, `configured: true`, secret never
in a response · `/providers` flag true (read from the DB) · PUT without
secret → 200 (kept) · PUT unknown provider → 404 · connect after save → 200
with `client_id=12345` in the authorize URL (the rebuild is live) · DELETE →
204, GET → unconfigured · DELETE again → 404 · unauthenticated PUT → 401.

### Docs
`api.md` Providers section: "Client configuration (server-level)" preamble +
the three endpoints. Next: M11d — the Server settings page and the per-
connection import-from floor in the UI.

## M11b — Credential resolution: key bootstrap, registry from the DB, env vars out (2026-08-28)

Second slice of M11: the running app now resolves its provider credentials
**from the database** — the `STRAVA_CLIENT_ID`/`STRAVA_CLIENT_SECRET`
environment variables are gone (pre-1.0, no deployments to protect), and the
Fernet key that protects the stored secrets self-bootstraps on first start.
Still no routes and no UI (those are M11c/M11d).

**Gates:** `make lint` green (ruff, mypy, tsc, eslint) · `make test` green
(178 passed: 171 pre-existing + 7 new bootstrap tests; 7 xfail contract
stubs) · api image rebuilt; live smoke passed (health, self-bootstrapped
key row, `GET /providers` reading `configured` from the DB).

### Key bootstrap (Q9 of the M11 design: ensure at startup, no env override)
- `app/security/secrets.py::ensure_secrets_box(session)` — reads the
  `secret_key` row from `server_settings`; on first use generates a Fernet
  key, stores it, commits. Called once from `create_app()` through a short
  session (startup is single-threaded → no locking; the DB `UNIQUE (key)`
  is the backstop). The resulting `SecretsBox` is process-wide on
  `app.state`, alongside the engine, limiter, and registry.
- Key rotation stays a recorded non-goal (it would mean a second key slot +
  re-encryption).

### Registry from the database
- New `app/providers/factory.py::build_provider_registry(settings, session,
  secrets_box)` — one adapter per provider with an **active** credential
  row: decrypts the stored secret and builds the adapter. A row whose
  secret cannot be decrypted (corruption, or a restore outliving its key)
  is **skipped with an ERROR log** — the provider reads as unconfigured and
  re-saving the credentials repairs it (Q18). `create_app()` now builds the
  registry this way instead of from env.
- `ProviderRegistry.close_all()` + a default no-op `ProviderAdapter.close()`
  (Strava's closes its httpx pool) — the machinery M11c's post-write
  rebuild uses to close displaced adapters.

### Env vars removed
- `strava_client_id`/`strava_client_secret` deleted from `Settings`,
  `docker-compose.yml`, and `.env.example`. `STRAVA_REDIRECT_URI`/
  `STRAVA_SCOPE`/`PUBLIC_BASE_URL` stay (deployment-URL concerns, not
  secrets). `installation.md` env table updated; the "Connecting Strava"
  how-to now points at the Server settings UI (the page itself lands in
  M11d, the API in M11c). `architecture.md` Providers section rewritten.

### Test bootstrap rework (conftest)
`create_app()` runs at **import time** and now touches the database, so the
test bootstrap moved to `pytest_configure`: it points `DATABASE_URL` at the
test database (env beats any `.env`) and creates/migrates it *before* any
test module imports `app.main`. The session-scoped `app` fixture imports
the app (after bootstrap); `client`/`uploads_dir` take it as a parameter.

### Tests (7 new, `tests/test_provider_bootstrap.py`)
Key get-or-generate (valid Fernet key stored; second call reuses it, exactly
one row) · registry from DB (no creds → empty; stored creds → adapter live
with the decrypted client id; soft-deleted row → not registered;
undecryptable secret → skipped + ERROR log) · `close_all` no-op on an empty
registry. Each test owns its deployment-table state (autouse truncate), so
the suite is order-independent.

### Live smoke (rebuilt api on :9090)
Health ok (version 0.3.0) · first boot **self-bootstrapped the key** — a
44-char `secret_key` row appeared in the live `server_settings` with no env
involvement · `GET /providers` (fresh smoke user) → `strava: configured
false`, read from the DB.

## M11a — Self-serve provider config: schema, DAOs, at-rest encryption (2026-08-28)

First slice of M11 (self-serve provider configuration, M11a–M11e): the deployment's own
OAuth client credentials become a database-stored entity instead of environment variables,
with client secrets encrypted at rest. This slice is **schema + code-side foundation only —
no routes, no UI, no behavior change yet** (those are M11b–M11e, per the grilling session
that shaped M11: DB is the only source of client creds, any authenticated user may configure,
Fernet key self-bootstraps in `server_settings`, sync floor is a user preference).

**Gates:** `make lint` green (ruff, mypy, tsc, eslint) · `make test` green (171 passed:
158 pre-existing + 12 new DAO/secrets + 1 new `sync_since` round-trip; 7 xfail contract
stubs for M11c/M11e) · migration verified up/down/up on a fresh database (scratch
`ht_m11a_verify`) · live DB converged, `make migrate` no-op, health OK on :9090.

### Schema (`20260827000001_provider_credentials.sql`)
- `server_settings` — deployment-level key/value settings (no `user_id`); first tenant is
  the Fernet key (row `secret_key`), generated on first use in M11b — no env var required.
- `provider_credentials` — the deployment's OAuth client per provider: `client_id`,
  `client_secret` (encrypted at rest), optional `display_name`; `UNIQUE (provider)`, FK →
  `providers.value`. Soft-deleting a row leaves user connections orphaned (sync paused
  until reconfigured) — the documented, non-cascading choice.
- `provider_accounts.sync_since timestamptz NULL` — the user-chosen **inclusive** lower
  bound of the sync walk (M11e): only activities started at or after it are imported;
  NULL = full history. Key decision: it is a **user preference, not sync state** — unlike
  `sync_cursor`/`last_sync_at` it survives reconnects.
- `STRAVA_CLIENT_ID`/`STRAVA_CLIENT_SECRET` env vars are dead (pre-1.0, no deployments):
  the database is the only source of client credentials. `STRAVA_REDIRECT_URI`/
  `STRAVA_SCOPE`/`PUBLIC_BASE_URL` stay env (deployment-URL concerns, not secrets).

### Code
- Models `ProviderCredential` + `ServerSetting` (+ `ProviderAccount.sync_since`); DAOs
  `ProviderCredentialDao` (get_active/get_any/add/save/mark_deleted — reconfigure reuses
  the soft-deleted row, since `UNIQUE (provider)` spans deleted rows) + `ServerSettingDao`.
- `app/security/secrets.py::SecretsBox` — Fernet encrypt/decrypt; `SecretsError` on
  wrong-key/tampered tokens. `cryptography` added as a runtime dependency.
- Test plumbing: the per-test TRUNCATE now covers the two deployment-level tables (they
  are not user-owned, so `CASCADE` from `users` never reaches them).

### Contract stubs (locked in now as `xfail(strict=True)`)
- `test_provider_config_api.py` → M11c: `GET/PUT/DELETE /providers/{p}/client/config`
  (masked view — secret never exposed; PUT-without-secret keeps the existing one; first
  PUT without one is 422; `GET /providers` reads `configured` from the DB).
- `test_provider_sync_lookback.py` → M11e: `POST /providers/{p}/sync` accepts an optional
  `since` (ISO date); the floor is the walk's only boundary — the sweep covers
  `[floor, newest]`, known ids skipped by dedup, cursor resume unchanged.

### Note (applied-migration hazard)
The WIP migration had already been applied to the local and test databases in an earlier
shape (before `sync_since` existed), so dbmate (version-tracked) skipped the updated
file. Both DBs were converged manually: test DB dropped + re-migrated fresh; live DB got
the one `ALTER TABLE provider_accounts ADD COLUMN sync_since` (data intact).

## M10d — Provider sync: pull a connected user's activities (2026-08-26)

The sync half of the provider story: a user can now pull their own activities
from a connected provider. A sync is a paged walk of the provider's activity
list (newest → older) that imports only what is new and resumes across runs.
This completes the provider integration (M10a–M10d).

**Gates:** `make lint` green (ruff, mypy 90 api files, tsc, eslint) · `make
test` green (158 tests: 149 pre-existing + 9 new sync tests) · api + web
images rebuilt; live smoke passed (health, sync 401/404 paths, UI sync
button).

### Sync service
- `ProviderSyncService` + `POST /providers/{p}/sync` (`SyncResultView`:
  `imported`, `skipped`, `last_sync_at`):
  - **Token handling** — when the cached access token is expired (or within a
    60s buffer), it is refreshed through the adapter and the **rotated pair
    is persisted** before the walk (Strava rotates refresh tokens; the latest
    is stored). A fresh token is used as-is.
  - **Paged walk** — walks from the stored `sync_cursor` (`None` = start at
    the newest), one adapter page per call. Every page id is checked against
    the global `(provider, external_activity_id)` dedup via a new
    `ActivityDao.exists_for_provider` (mirrors the partial unique index: not
    user-scoped, includes soft-deleted, exactly what the index enforces);
    unseen ids are fetched in full and imported through the shared
    `ImportService.import_parsed` (provider provenance, no file).
  - **Checkpointing and resume** — the cursor is committed after each full
    page. A run that finishes the walk clears the cursor and stamps
    `last_sync_at`; a run that hits the per-run cap (`MAX_SYNC_PAGES = 25`)
    or a provider failure keeps the cursor so the next run resumes where this
    one stopped. `last_sync_at` is stamped only when a run completes.
- **Rate limits** — `ProviderUpstreamError.retry_after_seconds` now yields a
  `Retry-After` header in the error envelope (the handler was generalized
  from the auth limiter's case). A 429 mid-walk stops the run, keeps the
  cursor, and tells the client when to retry.
- **nginx** — `proxy_read_timeout 300s` on `/api/` (a sync is one long
  request making many sequential provider calls; the default 60s would cut
  it off).

### Web UI
- Connected rows gain a **Sync** button (beside Disconnect): shows the
  per-run result ("Imported N new activities." / "All up to date.") or the
  API error on failure; the row's "Last synced" updates via query
  invalidation, and the activities feed is invalidated so new activities
  appear immediately.

### Tests (9 new, `tests/test_providers_sync.py`)
A stateful mock Strava over `httpx.MockTransport` that honors the `before`
cursor like the real API; a connected user is seeded via a direct session:
- Full history (2 pages, 102 activities) imports on the first sync: counts,
  feed total, cursor cleared, `last_sync_at` stamped, provider provenance
  (no `source_format`, external id recorded), 102 distinct detail fetches.
- Re-sync skips all 102 (0 imported).
- Partial run (page cap = 1) checkpoints the cursor; the next run resumes
  from it and finishes.
- Expired token → refresh (rotation persisted, fresh token used thereafter);
  fresh token → no refresh.
- Rate limit mid-walk (429 + Retry-After) → 502 `PROVIDER_ERROR` with a
  `Retry-After: 30` header, page 1 imported, cursor kept, `last_sync_at`
  untouched.
- 404 without a connection, 404 with a connection but unconfigured provider,
  401 unauthenticated.

### Live smoke (rebuilt stack on :9090)
Health ok; sync unauth 401; sync without a connection 404 `NOT_FOUND`; UI
bundle serves the Sync button. (The full sync walk is covered by the
mock-transport tests; a real round-trip needs a user's Strava credentials.)

## M10c — Provider OAuth: connect/disconnect routes, config wiring, profile UI (2026-08-26)

The connect half of the provider story: a user can now connect their own
Strava account from the profile page and disconnect it again. Strictly
opt-in and read-only; an instance without `STRAVA_CLIENT_ID`/`SECRET` is
unaffected (Strava reads as "not configured", 404 on connect). Sync itself
is M10d.

**Gates:** `make lint` green (ruff, mypy 89 api files, tsc, eslint) · `make
test` green (149 tests: 131 pre-existing + 18 new provider API tests) · api
+ web images rebuilt; live smoke passed (below).

### Fix first: Strava backward pagination (M10b follow-up)
- The M10b adapter sent the page cursor as Strava's `after` param. With
  newest-first results, `after=<page's oldest>` re-returns the *same* newest
  page — a sync walk over a full history would loop forever. The cursor is
  now sent as `before` (fetch the *older* page), so the walk reaches history
  and ends on a short page. Client, adapter, and both Strava test files
  updated (separate commit).

### Config wiring
- `Settings` gains `public_base_url` (the browser-reachable base URL; builds
  the OAuth redirect URI and the post-callback redirect) and the Strava app
  settings: `strava_client_id`, `strava_client_secret`, `strava_redirect_uri`
  (defaults to `{public_base_url}/api/v1/providers/strava/oauth/callback`),
  `strava_scope` (default `activity:read_all` — read-only). `.env.example` +
  compose env updated; `installation.md` gets the variables and a
  "Connecting Strava" how-to.
- `main.py::_build_provider_registry` registers an adapter per provider
  whose credentials are present; the registry is process-wide on
  `app.state` (adapters own their HTTP connection pools, like the engine).
  Unconfigured provider → 404 "not available on this instance".

### OAuth flow (state-bound user, redirect-based callback)
- New token kind on `TokenService`: `issue_oauth_state` /
  `verify_oauth_state` — a 10-minute JWT with a `purpose: oauth_state`
  claim. The connect URL's `state` param carries it; the callback verifies
  it, and **that is how the user is identified** — the callback is a plain
  browser redirect and carries no Authorization header. A session JWT
  presented as `state` is rejected (wrong purpose), as are forged/expired
  ones.
- `ProviderService` + routes under `/api/v1/providers`:
  - `GET /providers` — reference rows + `configured` flag. First read path
    on the `providers` reference table, so it got a `Provider` ORM model +
    DAO (same pattern as `activity_types` in M7).
  - `GET /providers/{p}/connect` — `{url}`: the authorize URL with state.
  - `GET /providers/{p}/oauth/callback` — exchanges the code, upserts
    `provider_accounts`, and 307s back to `/profile?connected={p}` or
    `/profile?connect_error={p}&reason=denied|state|error` (a browser flow
    cannot render a JSON error). The provider's `error=access_denied` maps
    to `reason=denied`.
  - `GET /providers/{p}/connection` — the connection view (provider,
    external_user_id, display_name, connected_at, last_sync_at — tokens
    never leave the API).
  - `DELETE /providers/{p}/connection` — best-effort provider-side revoke
    (failure is logged; the connection is dropped either way) + soft delete,
    204.
- Reconnection reuses the existing `(user, provider)` row: `UNIQUE
  (user_id, provider)` spans soft-deleted rows, so a fresh insert would
  collide. `ProviderAccountDao.get_any_for_user` +
  `ProviderAccountMapper.apply_credentials` (refreshes tokens, reactivates,
  resets `sync_cursor`/`last_sync_at` for a fresh full walk).
- External id resolution: the token-response athlete id when present, else a
  `fetch_identity` follow-up (keeps the NOT NULL column honest for other
  providers).

### Web UI (profile)
- `ConnectedAccounts` card on the Profile page: per provider — connect
  button (same-tab navigation to the authorize URL), connected state
  (display name, connected date, "Not synced yet" until M10d), disconnect
  with confirm, and "Not configured on this server" for unconfigured
  providers.
- One-shot OAuth result banner: `?connected=`/`?connect_error=` from the
  callback redirect are reported, then cleared from the URL. The same-tab
  hand-off makes the return a fresh page load, so no query-cache
  invalidation is needed.
- New hooks in `src/api/` (providers list, connection — a 404 reads as
  "not connected", connect, disconnect); `types.ts` mirrors the views.

### Tests (18 new, `tests/test_providers_api.py`)
Registry swapped on `app.state` with a `StravaAdapter` over
`httpx.MockTransport`: list (configured true/false, auth), connect URL
params, unknown/unconfigured 404s, callback success (row stored; view shape
with no token fields), invalid/missing state, session-JWT-as-state
rejected, denial, exchange failure (all the `reason=` redirects),
disconnect (204 → 404 after; the revoke request carried the refresh token),
and reconnect reuses the row (`connected_at` survives).

### Live smoke (rebuilt stack on :9090)
Unconfigured: `/providers` → `configured:false`; connect → 404 envelope;
callback with junk state → 307 `/profile?connect_error=strava&reason=state`;
connection → 404; unauth → 401. Configured (dummy credentials, api
recreated with env): `configured:true`, and the connect URL is the real
Strava authorize endpoint carrying the configured client_id, the derived
redirect_uri, the read-only scope, and a signed state. UI bundle serves the
new card.

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
  `before` as inclusive) is harmless — the dedup index imports each
  `(provider, external_activity_id)` once. (The first implementation sent the
  cursor as Strava's `after` param, which would have re-fetched the same page
  forever; fixed in M10c — see below.)
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
