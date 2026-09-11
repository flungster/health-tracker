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
| M11d | Server settings UI (provider clients) + import-from floor on connections | Done | 2026-08-29 |
| M11e | Sync lookback: import-from floor bounds the walk, per-run `since` rescan | Done | 2026-08-29 |
| M12 | Heart-rate zones: profile-relative, computed at view time (no fallback, table dropped) | Done | 2026-08-30 |
| M13a | User-configurable zones (I): profile settings (date of birth + custom tops), `zone_sources` + versioned snapshots, reference resolution in the profile view | Done | 2026-08-30 |
| M13b | User-configurable zones (II): detail computation against the resolved reference + versioned snapshots with supersede-on-change | Done | 2026-08-31 |
| M13c | User-configurable zones (III): profile UI — date of birth + custom zone tops, effective-reference display | Done | 2026-08-31 |
| M14a | Per-user unit system (I): profile setting — `imperial_units_enabled_at` timestamp + derived `units_system` on the request/view (no conversion yet) | Done | 2026-09-05 |
| M14b | Per-user unit system (II): API-side conversion — neutral view fields + `units` flag, imperial mi/ft/s-per-mi/lb/mph (exact factors), splits filtered per system | Done | 2026-09-05 |
| M14c | Per-user unit system (III): frontend — units context (localStorage + profile sync), unit-aware display everywhere, Profile toggle | Done | 2026-09-05 |
| M15 | Rowing: stroke rate end-to-end for indoor rowers — db no-op, api stats derivation + import pass-through (incl. sport-override bug fix), frontend no-op | Done | 2026-09-06 |
| M16 | Walking: pace displayed like running — db no-op, api view-layer `walking` metrics (unit-aware), frontend walking detail view (+ Vitest foundation) | Done | 2026-09-05 |
| M18 | Dashboard home page with period stats — `GET /activities/summary` (half-open UTC range) + dashboard UI; feed moves to `/activities` (ADR: `docs/adr/m18-dashboard-homepage.md`) | Done | 2026-09-09 |
| M19 | Polish batch: distance on the Rowing card + "How do I get these?" setup help in Server Settings (unparks two future-ideas) | Done | 2026-09-09 |
| M20 | TCX: vendor lap-distance fallback — Hydrow's `<Lap><DistanceMeters>` is now imported (parser fix, no db/api surface change) | Done | 2026-09-09 |
| M21 | Import provenance in the UI — provider badge on feed + detail (exposes `activities.provider`; no db change) | Done | 2026-09-09 |
| M22a | Cookie session auth for browser subresources — HttpOnly SameSite=Lax JWT cookie on login/register, `POST /auth/logout`, header-or-cookie resolver (ADR: `docs/adr/m22a-cookie-session-auth.md`) | Done | 2026-09-11 |
| M22b | Activity images (user upload): db + API core — `activity_images` + `image_sources`, magic-byte-validated uploads under `uploads/<user>/images/`, 4 routes (serve accepts the session cookie) | Done | 2026-09-11 |
| M22c | Activity images: web gallery on the detail page — thumbnails, add (drop or browse), enlarge lightbox, delete with confirm | Done | 2026-09-11 |

> 2026-08-25 — First release: **v0.2.0** tagged (see `CHANGELOG.md`); the
> deployed stack reports it at `GET /api/v1/health`.

> 2026-08-25 — Refactor + compliance batch (pre-M6): removed all third-party
> brand references, introduced a unit-of-work + dependency-injection +
> standardized-logging pattern for the API, and completed the dependency
> license audit (no AGPL / strong copyleft). See the entry below.

## M22c — Activity images: web gallery on the detail page (2026-09-11)

The UI half of M22: a **Photos** card on the activity detail page (after the
stat grid) with thumbnails, an add tile, click-to-enlarge and per-photo delete.

### Code (web)
- `api/types.ts`: `ActivityImageView` / `ActivityImagesView`.
- `api/hooks.ts`: `useActivityImages(activityId)` (query, keyed per activity),
  `useUploadImage` (multipart mutation) and `useDeleteImage`, both invalidating
  the gallery cache; plus `imageServeUrl(activityId, imageId)`. **No token in
  the URL** — `<img>` tags authenticate with the session cookie (M22a), which
  is exactly why that sub-milestone existed.
- New `components/ActivityImages.tsx`: responsive thumbnail grid; the add tile
  is a react-dropzone cell (multi-file, JPEG/PNG/WebP only — other files show
  an inline error naming the rejected file); each thumbnail has a hover delete
  (×) guarded by `window.confirm` like activity deletion; clicking opens a full-
  size lightbox (click-outside or Escape closes). Upload errors surface inline.

### Tests (+5, web now 35)
Thumbnails render with the cookie-served URLs + accessible alt text (filename or
fallback); empty state shows "No photos yet." and the add tile; delete fires only
after confirmation (and not when cancelled); no stray error note in the empty
state.

**Gates:** `make lint` green (tsc + eslint; api unchanged) · `make test`
green (**310 API** · **35 web**, +5).

### Live check (web rebuilt on :9090)
SPA serves; the new bundle carries the gallery ("Add photos", "No photos yet.",
"Remove photo"). The API half of the same flow (upload/list/cookie-serve/delete)
was verified end-to-end in M22b's live check.

## M22b — Activity images (user upload): db + API core (2026-09-11)

The local-first half of the parked "Activity images" idea: users attach photos
to their own activities. Bytes live on disk under `uploads/<user_id>/images/`
(mirroring the import file layout); the DB row is the authoritative record. The
Strava-fetch half stays parked behind its research gate — `source_url` and the
`image_sources` reference table are already in place for it.

### M22b.1 — db
New migration `20260911000001_activity_images.sql`:
- `image_sources` reference table (PK value + description, seeded with
  'uploaded', immutable — the provider half adds its values in a later
  migration, per the reference-table rule).
- `activity_images`: int id + public uuid; FK → `activities.uuid` (CASCADE);
  `source` FK → `image_sources`; `original_filename` NULL; **`stored_name`**
  (the on-disk file name = uuid + media-type extension, so every disk lookup is
  direct — no probing); `source_url` NULL (reserved for the provider half);
  `bytes > 0`; audit columns + updated_at trigger; partial index on
  `activity_id` for live lists. Soft delete.

### Code (api)
- Model + DAO (`IntIdUuidDao`: `add`, owner-scoped `list_for_activity`
  excluding soft-deleted rows in upload order, `soft_delete`).
- `ActivityImageService`: ownership goes through the activity (someone else's
  reads as 404, matching convention). Upload validates extension allowlist
  (JPEG/PNG/WebP) + non-empty + ≤ `MAX_UPLOAD_MB` + **magic-byte sniffing** —
  a renamed non-image is rejected, and the stored format follows the bytes, not
  the extension. Files go under `uploads/<user_id>/images/`. Serve = row checks
  + file existence → bytes + media type. Delete commits the row first, then
  removes the bytes best-effort (a failure only logs — the image is already gone
  from every view).
- Routes: `POST`/`GET /activities/{id}/images`, `GET .../images/{uuid}` (bytes),
  `DELETE` → 204. Serving accepts the header **or** session cookie — exactly
  what `<img>` tags need (M22a).

### Tests (+11)
Upload → disk layout + serve roundtrip (exact bytes, `image/png`); wrong
extension 422; non-image bytes behind a `.jpg` name 422 (the sniff); empty file
422; oversized 422 (settings override); someone else's activity → 404 and
nothing stored; list order = upload order; **serve with the session cookie only
(no Authorization header) — M22a integration**; delete → gone from list, disk
and serve; an image addressed through a *different* activity's URL → 404; row
intact but disk file missing (simulated corruption) → 404.

**Gates:** `make lint` green (ruff, mypy 109 api files; tsc + eslint) · `make
test` green (**310 API**, +11 · **30 web**).

### Live check (api rebuilt on :9090)
Health ok. Smoke account: imported the sample GPX, uploaded a 70-byte PNG →
201 (`source=uploaded`, right filename/bytes); list shows one item; **serving
with the cookie only (no Authorization header) returned 200 `image/png` with
identical bytes**; delete → 204, then serve → 404. The imported smoke activity
was soft-deleted afterwards (the M22a account is kept for future live checks).

## M22a — Cookie session auth for browser subresources (2026-09-11)

Foundation for M22 (activity images): `<img>` tags cannot set the
`Authorization: Bearer` header, so owner-scoped image serving needs a
header-less auth path. The session JWT is now mirrored into an HttpOnly cookie;
**Bearer stays primary**, the cookie is a fallback (ADR:
`docs/adr/m22a-cookie-session-auth.md`, decision made with the user — query-param
JWT and short-lived signed URLs were considered and rejected).

### Code (api + web)
- New `app/security/cookies.py`: name/path constants (`ht_session`,
  `Path=/api/v1`) + set/clear helpers — `HttpOnly; SameSite=Lax`, plus `Secure`
  when the new setting `SESSION_COOKIE_SECURE=true` (default false for plain-HTTP
  homelab deployments). Max-Age mirrors the JWT TTL.
- `POST /auth/login` + `/register`: JSON response unchanged; additionally set the
  cookie mirroring the issued token. New `POST /auth/logout` → 204 expires it
  (the bearer token itself is stateless and stays valid until its TTL — no
  revocation introduced; documented trade-off).
- `get_current_user`: one shared resolver — Bearer header first, then the cookie.
  Applied to **all** endpoints; SameSite=Lax is what makes that safe (cross-site
  subrequests don't send it — see the ADR's security analysis).
- SPA: `logout()` calls `POST /auth/logout` best-effort before clearing local state.

### Tests (+4)
- login/register set the cookie (value equals the body token; flags: `httponly`,
  `samesite=lax`, `path=/api/v1`).
- A cookie-only request (no Authorization header) authenticates to `/users/me`.
- logout → 204 + expired cookie; the following cookie-only request is 401.

**Gates:** `make lint` green (ruff, mypy; tsc + eslint) · `make test` green
(**299 API**, +4 · **30 web**).

### Live check (api + web rebuilt on :9090)
Throwaway smoke account: register → `set-cookie: ht_session=…; HttpOnly;
Max-Age=2592000; Path=/api/v1; SameSite=lax`; `/users/me` with the cookie only
(no header) → 200, correct user; `POST /auth/logout` → 204 + cookie expired;
subsequent `/users/me` with the stale jar → 401.

## M21 — Import provenance in the UI (2026-09-09)

First of the two ideas parked on 2026-09-09 (`docs/future-ideas.md`): the UI
now shows where an activity came from. Provider-fetched activities carry their
provider's name (e.g. **Strava**) beside the sport badge on feed cards and in
the detail header; file imports carry no badge — a bare card is one you uploaded.

### M21.1 — db (verified no-op)
`activities.provider` (+ `external_activity_id`) has been stored since M10a —
this milestone exposes the existing column; no migration needed.

### Code (api + web)
- Views: `provider` (value string or null) on the list item and detail views,
  beside `source_format` / `original_filename`; mapper pass-through. The two
  provenance pairs are mutually exclusive by construction (file vs provider).
- Web: new `ProviderBadge` — an outline pill, deliberately dot-less to read as
  different from the sport badge; renders nothing when null. Placed beside
  `SportBadge` on the feed card and detail header; types moved in lockstep so
  `make up` stayed green.

### Tests
- API: the GPX import pins `provider: null`; the M10d sync-walk test now
  asserts a synced activity's list item *and* detail expose `provider: "strava"`.
- Web (+2): the badge renders the capitalized value; null → empty DOM.

**Gates:** `make lint` green (ruff, mypy 102 api files; tsc + eslint) · `make
test` green (**295 API** — assertions added to existing tests, no new count ·
**30 web**, +2) · no schema change (verified no-op above).

### Live check (api + web rebuilt on :9090)
Health ok, version unchanged. A provider row was seeded for the smoke account
(a clone of an existing run tagged `provider='strava'`, removed afterwards): the
list shows `"provider": "strava"` on exactly that row and `null` on every file
import; the detail shows `"provider": "strava"` with a clean provenance pair
(`source_format: null`, `original_filename: null`). SPA serves.

### Docs
`api.md`: list/detail examples gain the provenance fields + a note on their pair
semantics · `usage.md`: feed and detail-header bullets mention the badge.

**Remaining from that parking session:** "Import duplicate detection with
user-confirmed overwrite" — still parked (needs its design decisions first).

## M20 — TCX: distance for vendor lap elements (Hydrow) (2026-09-09)

Started from a user report: the only rowing activity (imported from a Hydrow
TCX) showed no distance — not on the M19 card, not in the stat grid.

**Diagnosis:** `activities.distance_m` was NULL — it was never stored, so the
views were correctly rendering null (not zero). The TCX parser reads lap
distance from the spec element `<TotalDistanceMeters>` (absent in Hydrow files)
and otherwise derives distance from GPS trackpoints (indoor rower: no
coordinates). The file *does* carry the distance — as a plain `<DistanceMeters>`
direct child of `<Lap>` (the exact total), with the same tag reused on each
trackpoint for cumulative sample values — and all of it was dropped.

**Fix (parser only, at import time):** lap distance now falls back to the
vendor's `<DistanceMeters>` when `TotalDistanceMeters` is absent — **direct
children of `<Lap>` only**, so a descendant lookup can never mistake the first
trackpoint's cumulative value (0) for the lap total. Precedence: spec element >
vendor variant > GPS derivation > null. No DB change, no API surface change —
existing imports are untouched (imports stay immutable; a re-upload picks the
value up).

**Gates:** `make lint` green · `make test` green (**295 API + 28 web**, +4: new
Hydrow-style `rower_sample.tcx` fixture — parser test pinning distance 875.42
and null moving time (the file carries no `MovingTime`, so "—" is correct, not
a gap); an inline TCX carrying *both* elements proving the spec element wins and
sample values are ignored; a file with neither → distance null; API integration:
fixture imported with the rowing override → detail `distance` 875.42).

### Live check (api rebuilt on :9090)
The user's actual Hydrow TCX re-imported (rowing override, smoke account):
`distance: 2.4092 mi` for the imperial caller — exactly **3877.28 m**, the lap
value in their file, through M14's exact mile factor. The old activity row still
has no distance (imports are immutable) — re-uploading it is the backfill.

### Docs
`import-formats.md`: TCX section now records the vendor fallback and why it is
direct-children-only.

## M19 — Polish batch: rowing distance + Strava setup help (2026-09-09)

The two smallest parked ideas, shipped together as one polish milestone
(unparked from `docs/future-ideas.md`, whose entries were removed): distance
rowed on the **Rowing** card, and "How do I get these?" setup help in Server
Settings. Both were parked as frontend-only; both stayed that way.

### M19.1 — db + api (verified no-op)
`ActivityDetailView.distance` already carries the unit-aware distance of every
activity (M14), and no endpoint changes for either item — nothing to migrate,
nothing new on the wire.

### M19.2 — frontend (done)
- **Rowing card**: `RowingDetail` now takes the detail's `distance` and shows a
  unit-aware **Distance** metric (5th tile, like WalkingDetail's in M16) — the
  sketch's "render the detail-level `distance`" option, i.e. no view-shape
  change at all. Feed cards already show distance for every sport, so nothing
  there (the "optionally on feed cards" part needed no work).
- **Server settings**: each provider card (Strava today) gains a collapsible
  **"How do I get these?"** block — the three setup steps (create the app with
  Read scope at strava.com/settings/api, copy ID/secret into the card, add this
  server's callback URL to Redirect URIs) with **this deployment's actual
  callback URL** rendered from `window.location.origin`, instead of a
  `{PUBLIC_BASE_URL}` placeholder.

**Gates (final):** `make lint` green · `make test` green (**291 API + 28 web**,
+3 RowingDetail cases: metric distance, imperial-converted distance with stroke
rate untouched, em-dash on null) · no schema change (verified no-op above; API
image untouched — only web rebuilt).

**Test hygiene fix found along the way:** `SportDetails.test.tsx` never
unmounted renders (no vitest globals → testing-library's auto-cleanup never
registered); earlier assertions only passed because their texts were unique.
`afterEach(cleanup)` added — the new duplicate-text rowing assertions would not
have survived without it.

### Live check (web rebuilt on :9090)
Health ok, version unchanged (0.3.0). Served bundle carries "How do I get
these?" and the strava.com/settings/api link. A rowing-imported fixture (the M15
override trick) returns `distance: 3.1406` in miles for the still-imperial smoke
user — exactly what the new card tile renders (3.1 mi) alongside its stroke rate
and 500 m split.

### Docs
`usage.md`: rowing card now lists distance in the sport-metrics line; Server
settings section notes the per-card help block with this server's callback URL.

## M18 — Dashboard homepage with period stats (2026-09-09)

The logged-in home page answers "what did I do this day / week / month /
year?" at a glance. All decisions are locked in the ADR
(`docs/adr/m18-dashboard-homepage.md`, grilled 2026-09-08): seven stat cards,
one distance-over-time chart, current-period-only (Day / Week / Month / Year),
client-side period selection. The feed keeps its behavior at `/activities`; the
brand in the header links to the dashboard.

### M18.1 — db (verified no-op)
Every input is an existing stored column (`activities.*`,
`strength_activity.total_weight_kg`) — no migration needed.

### M18.2 — api (done)
- `GET /api/v1/activities/summary?start=…&end=…` — required ISO 8601 UTC
  instants (naive = UTC), half-open `[start, end)`, 422 on malformed/inverted
  ranges. Scoped by `user_id`; soft-deleted rows excluded like everywhere else.
- DAOs: `ActivityDao.period_totals` (count + sums/mean in one aggregate),
  `sport_counts_for_period`, `distance_trend_for_period` (UTC calendar buckets)
  and `StrengthActivityDao.total_weight_for_period` (joins through
  `activities` for user scoping + the window).
- Pure helpers in `activity_stats`: `trend_buckets` (day buckets up to ~62
  days, month beyond — the year view) + `zero_fill_trend` (gaps are 0.0, so
  the series is continuous) + the raw-SI `PeriodSummary` dataclass.
- View layer: `ActivityPeriodSummaryView` (+ count/trend-point views); the
  mapper converts per M14 (nulls pass through — **null-not-zero**: a metric
  with no contributing data is `null`, only the count is always numeric).
- Per ADR: avg HR = simple mean of per-activity averages (whole bpm);
  `weight_lifted` is the summed strength volume and stays `null` until an
  import source provides weights (none do yet). Steps excluded — no parser or
  provider writes them.

**Gates:** `make test` green (**291 passed**, +18: 7 summary API tests —
metric exactness, null-not-zero on an empty period, sum/mean across two sports,
imperial conversion of value *and* trend, monthly buckets on a year range, 422s
on malformed/inverted ranges, soft-delete exclusion — 7 pure bucketing/zero-fill
tests, and a new `test_strength_activity_dao.py` pinning the weight sum's user
scoping, window and null-not-zero rules) · `make lint` green.

### M18.3 — frontend (done)
- Routing: `/` → new **Dashboard** page; the feed moves to `/activities`
  (unchanged). The brand is now a link home; the detail page's "Back to
  activities" and post-delete redirect follow it. Login/register already land
  on `/` (now the dashboard).
- `src/periods.ts` (pure, unit-tested): the four segments; boundaries in the
  **local** timezone (midnights), week = Monday–Sunday fixed; `periodRange`
  returns the half-open UTC instants. Selection is display-only state per the
  ADR: URL param `?period=…` backed by localStorage (`health-tracker.dashboard.
  period`, default **Week**) — no server setting, unlike units (the API needs
  none here; the client computes `[start, end)`).
- **DashboardPage**: seven display-only cards (activities + per-sport chips,
  moving time, distance, elevation gain, calories kcal — never converted, avg
  HR bpm, weight lifted kg/lb) with null → "—", the **Distance over time**
  chart (hidden on Day; day bars for Week/Month, month bars for Year), and one
  **View all activities** link to the unfiltered feed. Values render in the
  response's `units` system, like every other view (M14).
- Chart: `DistanceTrendChart` in `Charts.tsx` (bars, unit-aware tooltip via
  the existing format helpers). Hook: `usePeriodSummary(start, end)` — its key
  is under the `"activities"` prefix, so imports/syncs refresh it for free.

**Gates (final):** `make lint` green (ruff, mypy 102 api files — strict on the
new path; tsc + eslint) · `make test` green (**291 API + 25 web**, +10: period
boundaries incl. Monday/Sunday edges and the year-crossing week, localStorage
fallback) · no schema change (M18.1 verified no-op; `migrate up` idempotent on
the live stack) · api + web images rebuilt; live check passed (below).

### Live check (api + web rebuilt on :9090)
Health ok, version unchanged (0.3.0). Fresh smoke user uploads
`run_sample.gpx`: metric June summary — count `{total: 1, running: 1}`, moving
1480 s, distance **exactly** the detail's stored value (5054.329… m),
elevation 120.0, calories `null` (the GPX carries none — null-not-zero),
weight lifted `null`, 30 daily buckets with the activity's day holding it all ·
empty July → total 0, every metric `null`, trend `[]` · imperial toggle →
distance 3.1406 mi, elevation 393.7 ft (M14b's exact numbers), trend converted
too · malformed `start` 422s, inverted range 422s with the envelope · served
bundle carries "Distance over time", "View all activities" and the period
localStorage key; `/activities` serves 200. Milestone closed 2026-09-09 after
sign-off.

### Docs
`api.md`: the summary endpoint (range semantics, null-not-zero, trend bucketing)
+ unit-table rows for the new fields · `usage.md`: a Dashboard section, feed at
`/activities`, getting-started step 3 · `architecture.md`: page list + a note on
the display-only period state.

## M16 — Walking: pace displayed like running (2026-09-06)

Walking gets a first-class detail view. The pace is **computed at read time**
from the stored moving time and distance (locked decision: API view layer, so
walking is served by the API like every other sport — no new table).

### M16.1 — db (verified no-op)
`activities` already carries `moving_seconds` + `distance_m` since M3 — the
pace is derivable at view time; no migration needed.

### M16.2 — api (done)
- `WalkingMetricsView` (`avg_pace_seconds`) added to the detail view, emitted
  for every walk — even one without distance (pace then null), preserving the
  "exactly one sport object per activity" convention.
- `ActivityMapper._walking_avg_pace_s_per_km`: null-safe derivation
  (moving ÷ distance → s/km, rounded to a tenth like stored paces); the value
  then flows through `display_pace_seconds`, so imperial callers get s/mi by
  the exact mile/km factor — the derived value converts at read time just like
  stored ones.

**Gates:** `make test` green (**273 passed**, +2: metric derivation on a
walk-imported fixture — 1480 s over ~5.05 km = exactly 292.8 s/km — and the
imperial conversion of that derived pace; plus a `walking: null` assertion on
the run import) · `make lint` green.

### M16.3 — frontend (done)
- **Vitest foundation** (the deferred Step 1): `vitest` + `jsdom` +
  `@testing-library/react` added to web devDeps; vitest configured in
  `vite.config.ts` (jsdom env, `src/**/*.test.{ts,tsx}`); new `"test": "vitest run"`
  script; `make test` now runs the API suite *and* the web unit tests.
- **WalkingDetail** (`web/src/features/SportDetails.tsx`): avg pace (unit-aware
  `/km`/`/mi`) + distance; dispatched from the detail page for `walking`
  activities (leaving walking out of the generic-fallback condition). Types:
  `WalkingMetricsView` + `ActivityDetailView.walking`.

**Gates (final):** `make test` green (**273 API + 15 web** — format helpers and
WalkingDetail in metric/imperial/null-pace) · `make lint` green. Live on :9090:
both images rebuilt; a walk-imported sample shows `walking.avg_pace_seconds` of
292.8 (metric) and 471.2 s/mi after the imperial toggle; bundle confirmed to
carry the new view. Milestone closed 2026-09-05 after sign-off.

## M15 — Rowing: stroke rate end-to-end (2026-09-06)

Rowing milestone for indoor rowers (the operator's Hydrow exports to Strava).
Structure per the new cadence: one activity type per milestone, sub-milestones
db → api → frontend with a pause after each. **Finding that shaped the slice:**
rowing stroke rate was dropped at import from *every* source — the columns and
`ParsedSportMetrics.stroke_rate_*` fields all existed, but no code path ever
populated or persisted them (RowingDetail's stroke-rate metrics always rendered "—").

### M15.1 — db (verified no-op)
`rowing_activity` already carries `stroke_rate_avg/min/max_spm` +
`split_500m_seconds` since the M3 schema — no migration needed (additive-only
was the requirement; none was necessary).

### M15.2 — api (done)
**Decision: three-level precedence in `ActivityStatistics`, mirroring the
cycling-power pattern — no parser changes needed:**
1. explicit `sport_metrics.stroke_rate_*` (a first-priority hook for a decoder
   that ever exposes stroke rate directly);
2. per-sample cadence — rowing devices export their stroke rate in the record's
   "cadence" field (fitdecode 0.11 has no stroke-rate fields at all, and our
   FIT parser already reads record `cadence` into trackpoints);
3. summary-level cadence — Strava reports a rower's stroke rate as the
   activity's `average_cadence` (already converted to `cadence_avg_rpm`; the
   existing rowing fixture test pins 26.4 → 26).

**Latent bug fixed along the way:** stats were computed against
`parsed.sport_type` *before* the sport override/default was resolved, so an
import overridden to rowing (or cycling) never ran that sport's stat branches.
The resolved sport is now assigned to the parsed activity before `compute()`.

**Gates:** `make test` green (**271 passed**, +6: five stroke-rate precedence
unit tests, one API integration — `run_sample.gpx` imported with a rowing
override yields avg 171 / min 170 / max 172 spm plus the 500 m split) ·
`make lint` green (ruff, mypy strict on the new code path, tsc/eslint).

### M15.3 — frontend (confirmed no-op)
No change made: `RowingDetail` already renders stroke-rate avg/min/max and the
500 m split, and `usage.md` already describes them — the fix was entirely in
the import path. Milestone closed 2026-09-06 after sign-off.

## M14c — Per-user unit system (III): frontend display + the toggle (2026-09-05)

Final slice of M14: the UI now renders unit-bearing values in the caller's
display system and offers a **Units of measurement** card on the Profile page.
This completes M14 end-to-end — metric/imperial is a per-user, server-stored
preference that converts everything at read time and never touches stored data.

**Decisions (locked in the planning session):**
- One `UnitsProvider` owns the display system for the whole app. It **seeds from
  localStorage** (`health-tracker.units`, metric default) so the correct units
  pre-paint before any request, then **follows the profile** (`units_system`) —
  which is the source of truth and what every other tab/profile-save re-syncs to.
- The toggle **optimistically flips** state + localStorage on save success, so the
  whole UI (feed cards, detail stats, splits, sport metrics) switches instantly;
  the `["profile"]` invalidation re-syncs it. No live cross-tab sync — a later
  load re-reads the profile (documented in usage.md).

**Gates:** `make lint` green (ruff, mypy 102 api files — unchanged this slice;
tsc + eslint on the new/changed web code) · `make test` green (**265 passed**,
API unchanged; the frontend is gated by tsc/eslint) · web image rebuilt and the
units UI confirmed present in the served bundle (`health-tracker.units`, "Units of
measurement", per-kilometre/per-mile). No backend change in this slice, so no DB
verification was needed.

### Code (web only)
- `src/units/context.tsx` (new): `UnitsProvider` + `useUnits()`. Seeded from
  localStorage, synced to the profile (the query is enabled only while
  authenticated), and `setUnits` writes both state and localStorage. Mounted in
  `main.tsx` inside the providers (needs auth + query client).
- `src/format.ts`: `formatDistance` / new `formatElevation`, `formatWeight`, and
  `paceSuffix` all take a `Units` argument — metric keeps its exact prior output,
  imperial adds miles (1 dp), whole feet/lb with grouping, and a `/mi` suffix.
- Display sites now read `useUnits()`: the feed card's distance, the detail stat
  grid (distance / elev gain / avg pace), running paces and strength volume in the
  sport panels. `SplitsTable` is simplified to a single table — it renders whatever
  system the API returned (M14b already filters server-side), keyed off `split_type`.
- `src/api/hooks.ts`: `useProfile` gained an optional `enabled`; `ProfileUpdateInput`
  fields became individually omittable (matching the server's "omitted = keep" rule)
  and gained `units_system?: Units`.
- `src/pages/ProfilePage.tsx`: a **Units of measurement** card with metric/imperial
  buttons. Picking one PATCHes only `units_system` and flips the UI on success; a
  separate mutation instance keeps its pending state off the heart-rate form.

### Docs
`usage.md`: a new *Units of measurement* section (what converts, what doesn't —
calories/HR/cadence/power/time never do; rowing's 500 m split stays in metres —
and the "stored data is never changed" guarantee), plus a Profile bullet and an
updated Splits note (one table in your system; sub-tenth-of-a-unit edge).

**M14 is complete.** All three slices are Done; the unit system ships as a
per-user, read-time-converted preference with no schema migration beyond M14a's.

## M14b — Per-user unit system (II): API-side conversion + view shape change (2026-09-05)

Second slice of M14: activity views now convert to the caller's display unit
system in the API (never the frontend). Unit-bearing view fields carry neutral
names (`distance`, `elevation_gain`, …); each list/detail/trackpoints response
carries a `units` flag saying which system its values are in. Imperial users get
miles / feet / s-per-mile / lb / mph using **exact** factors (the API sends
unrounded values — rounding is a client concern, M14c). Splits are filtered to
the caller's system server-side (both units were already precomputed at import).
**Zero schema changes in this slice — storage stays SI**; the TS types moved in
lockstep so `make up` stayed green, and display logic + the toggle are M14c.

**Decisions (locked in the planning session):**
- View shape: unit-neutral fields + a `units` flag on `ActivitiesListView`,
  `ActivityDetailView` and `TrackpointsView`. No reference table (no column
  stores the value); `SplitsView` is unchanged — rows self-describe via their
  existing `split_type`.
- Conversions: distance m→mi (`/1609.344`), elevation/altitude m→ft
  (`/0.3048`), running pace s/km→s/mi (`×1.609344`), weight kg→lb
  (`/0.45359237`), speed m/s→mph — all exact definitions, so no information is
  lost and toggling back restores the stored value *exactly*. Never converted:
  `calories_kcal`, power W, bpm/rpm/spm, durations; rowing's
  `split_500m_seconds` stays 500-m-based in both systems (the standard rowing
  pace metric). Trackpoints convert too (altitude/speed) for a consistent API.
- Splits: the service returns only the caller's system's precomputed rows; an
  activity shorter than a tenth of one unit has none for that system (the
  documented edge — an imperial caller sees no splits on a ~130 m activity).

**Gates:** `make lint` green (ruff, mypy 102 api files — new `app/schemas/units.py`
— tsc, eslint) · `make test` green (**265 passed** — +13 new: 10 pure conversion
tests, 3 imperial API tests) · no schema change (nothing to verify up/down — the
M14a migration already landed) · api image rebuilt; live check passed (below).

### Code
- `app/schemas/units.py` (new, pure): `UnitSystem` enum, `units_for(instant)` —
  the single derivation point (the user mapper now delegates to it) — and the six
  `display_*` conversion helpers (exact factors, None passthrough). Unit-tested in
  isolation.
- Views: field renames per the plan (`distance_m`→`distance`, `elevation_gain_m`
  →`elevation_gain`, running `_s_per_km`→`_seconds`, `total_weight_kg`
  →`total_weight`, trackpoint `_m`/`_mps`→`altitude`/`speed`) + `units` on the
  three list/detail/trackpoints views. Docstrings spell out "km when metric, mi
  otherwise".
- `ActivityMapper`: the view methods take a `UnitSystem` and call the helpers;
  `to_detail_view` gained it as its last parameter.
- `ActivityService`: resolves the caller's system per request — `get_detail` now
  loads the profile **once** and derives both the zone reference *and* the unit
  system from it (no extra query), filters splits to that system (`_splits_for`);
  `list_for_user` returns `(activities, total, units)`; `get_trackpoints` returns
  `(points, units)`. The route layer passes the flag through unchanged.

### Tests (13 new)
- `test_units.py` (+10): `units_for(None)`/set; None passthrough on every
  converter; metric identity; the exact `x/x == 1.0` identities (one mile in
  meters → exactly 1 mi; one foot, one pound); a distance round-trip at
  `rel=1e-12`; pace scales by the exact mile/km ratio (300 s/km → 482.8032
  s/mi); speed→mph and kg→lb at `rel=1e-9`.
- `TestUnitsImperial` in `test_activities.py` (+3): imperial converts the detail,
  list feed and trackpoints against exact expected values captured from a metric
  read (distance/elevation/pace + per-sample altitude/speed, same order); toggling
  back to metric restores the stored value **exactly** (equality, not approx —
  proof storage was never touched); and the sub-tenth-of-a-mile edge (a ~132 m
  inline GPX) has km rows in metric but **no** splits at all in imperial. (The FIT
  fixture can't demo that edge: its trackpoint path is longer than its summary
  distance — noted in the test.)

### Live check (api rebuilt on :9090)
Health ok, version unchanged (0.3.0). Fresh smoke user uploads `run_sample.gpx`:
metric baseline — distance 5054.33 m, elevation gain 120 m, avg pace 292.8 s/km,
splits km-only · PATCH imperial → `units: "imperial"` — distance 3.1406 mi,
elevation gain 393.7 ft, avg pace 471.2 s/mi, splits mi-only (n=4); the list feed
converts too; a trackpoint altitude reads 131.23 ft for its stored 40 m · PATCH
back to metric → the exact stored values (5054.33 m, km rows) return — no drift.

### Docs
`api.md`: an Activities "Unit systems" preamble (the conversion table + the
never-converted list), updated examples for list/detail/trackpoints/splits, and a
note on per-system split filtering incl. the tenth-of-a-unit edge · `data-model.md`
unchanged (the columns stay SI; the M14a row already records that conversion is a
view-layer concern). No `usage.md` change yet — the user-facing toggle lands in
M14c.

**Next: M14c — frontend unit-aware display + the toggle**: a units context
seeded from localStorage (metric default) and synced on profile save, unit-aware
`format.ts`, label updates across feed/detail/splits/charts, and the "Units of
measurement" card on the Profile page.

## M14a — Per-user unit system (I): the setting, stored as a timestamp + profile API surface (2026-09-05)

First slice of M14 (metric/imperial display units). A user can now choose a
display unit system on their profile. It is stored as **a timestamp, not a
boolean** — `user_profiles.imperial_units_enabled_at`: NULL = metric (the
default), set = imperial in effect *since* that UTC instant — so the column
answers both "is it on?" and "when was it enabled?". This slice is **setting +
API surface only: no value conversion yet** (M14b) and no UI (M14c).

**Decisions:**
- One nullable timestamp, two states. Toggling back to metric clears the column;
  the last enable instant is intentionally dropped (a second column could be added
  later if history ever matters). No boolean anywhere.
- `PATCH /users/me/profile` gains optional `units_system: "metric" | "imperial"`
  following the repo's per-field semantics — omitted = keep; but because metric *is*
  the default, both `"metric"` and an explicit `null` clear back to it (no third
  state exists). Any other value → 422 `VALIDATION_ERROR`.
- `ProfileView.units_system` is **derived** (`"imperial"` when the timestamp is set,
  else `"metric"`), never null. The raw instant stays queryable in the DB; it is not
  exposed through any API (the setting's "when" is a data-level question).
- No reference table: no column stores the value, so the enum-like-column rule does
  not trigger; the request uses a `Literal`, the view a derived string.
- **Storage stays SI.** No activity row is touched by this feature — conversion to the
  user's display system happens at the API view layer (M14b).

**Gates:** `make lint` green (ruff, mypy 101 api files, tsc, eslint) · `make test`
green (**250 passed** — +8 new: 6 profile API cases, 2 column DAO tests) · migration
verified up/down/up on a fresh scratch DB (`ht_m14a_verify`, dropped after) · live
stack migrated in place, api image rebuilt; live check passed (below).

### Migration
`20260905000001_imperial_units_setting.sql` — `user_profiles.imperial_units_enabled_at
timestamptz NULL` + column comment; down drops the column. Verified: fresh DB → up
(all migrations) → shape checked (timestamptz, nullable, comment present) → down 1
(column gone) → up (column back).

### Code
- `UserProfile` model: the nullable timestamptz column + docstring note (display-only,
  storage stays SI).
- `UserProfileDao.apply_health_settings` gains the required kwarg — its contract is
  unchanged (full resolved state; `None` = deliberate clear). **Caught by the new
  tests:** the first draft accepted the parameter without persisting it.
- `ProfileUpdateRequest.units_system: Literal["metric", "imperial"] | None`; the
  service maps it (provided `"imperial"` → `now(UTC)`; explicit `null`/`"metric"` →
  clear; omitted → keep) — written in the same per-field style as its siblings.
- `UserMapper.units_system_for(profile | None)` (the one derivation point) + the view
  field on both profile-view paths.

### Tests (8 new)
- `test_users.py` (+6): the default metric is pinned by `EMPTY_PROFILE`'s exact-shape
  assertion (every profile test now carries it) · imperial round-trip + re-read, with
  all other fields untouched · reset via `"metric"` and via `null` (same two-state
  operation) · omitted field keeps imperial while updating max HR · unknown value →
  422 `VALIDATION_ERROR` · and the "when" case: reading
  `imperial_units_enabled_at` straight from the DB — a fresh UTC instant after enabling,
  NULL again after resetting.
- `test_user_profile_dao.py` (new file, +2): a fixed instant round-trips through
  `apply_health_settings` (including row creation on first write) and a deliberate clear
  returns the column to NULL; a user with no profile row reads as metric.

### Live check (api rebuilt on :9090)
Health ok, version unchanged (0.3.0). Fresh smoke user: GET profile → `units_system`
"metric" · PATCH `"imperial"` → 200 "imperial", persists on re-read · DB column stamped
`2026-09-06T05:16Z` (UTC) · PATCH `"metric"` → "metric", column NULL · explicit `null`
resets identically · unknown value 422s.

### Docs
`data-model.md`: `user_profiles` column row + migration table row (noting storage stays
SI) · `api.md`: profile GET (derived field) and PATCH (`units_system` semantics, incl.
the null = reset rule). No UI change yet (M14c).

**Next: M14b — API-side conversion + view shape change**: unit-neutral field names
(`distance`, `elevation_gain`, …) with a `units` flag on the list/detail/trackpoints
views; imperial users get miles / feet / s-per-mile / lb (exact factors, no rounding in
the API); splits are filtered to the user's system server-side (both precomputed units
already exist). TS types move in lockstep so `make up` stays green; display logic and
the toggle land in M14c.

## M13c — User-configurable heart-rate zones (III): profile UI for the zone reference (2026-08-31)

Third and final slice of M13: the **Profile** page now exposes everything that
shapes heart-rate zones — date of birth and four custom zone tops alongside the
existing max/resting HR — plus a line naming which reference is currently in
effect. The API needed no change (M13a's request/view already carried these);
this is pure frontend.

**Decisions:**
- The card shows the **effective reference** from the server-computed profile
  fields (`zone_source` / `effective_max_heart_rate` / `age`) — "Zones are
  computed from your custom boundaries (…)" / "(190 bpm)" / "age — max HR 178
  (220 − age, currently 42)" / "No zone reference is set yet". No precedence
  logic in the client.
- **All-or-nothing + ascending** custom zones are validated locally for a
  friendly inline error (the server re-validates and owns the envelope); all
  four blank clears them. The form keeps its existing shape: it always sends
  every profile field, empty → `null`.

**Gates:** `make lint` green (ruff, mypy 101 api files unchanged, tsc, eslint) ·
`make test` green (**242 passed** — no API change in this slice) · web image
rebuilt; live check passed (below).

### Code (`web/src/` only)
- `api/types.ts::ProfileView` gains the six stored fields plus the three
  computed reference fields (mirrors M13a's view).
- `api/hooks.ts::useUpdateProfile` now takes a named `ProfileUpdateInput` (all
  seven fields) instead of the two-field inline type.
- `pages/ProfilePage.tsx` — the Heart-rate zones card gains: a date-of-birth
  field (optional; helper text explains the `220 − age` fallback), a Custom
  zone boundaries fieldset (four bpm inputs, helper text: priority over max HR,
  all-or-blank to clear), the effective-reference line above the form, and a
  local validation state rendered through `ErrorNote`. Prefill extends to all
  new fields; the existing save/invalidate flow is unchanged.

### Live check (web rebuilt on :9090)
SPA serves `/profile` · the new bundle carries "Custom zone boundaries",
"Date of birth", and the ascending/completeness validation strings · API round-
trip for this exact payload shape (all fields, nulls) already covered by the
M13a/M13b API tests. Health ok, version unchanged (0.3.0).

### Docs
`usage.md`: Heart-rate zones section now points at the Profile page for all
three references (+ "enter all of them or none" and the effective-reference
line), Profile bullet lists the new fields, activity-detail note says "needs a
zone reference set on your profile" instead of only max HR.

**M13 is complete** (M13a–M13c): a user can define custom zones, or rely on
their max heart rate / age; every activity's zone chart follows the active
reference immediately, with a versioned per-activity history of what was shown.

## M13b — User-configurable heart-rate zones (II): reference-based computation + versioned snapshots (2026-08-31)

Second slice of M13: the activity detail endpoint now computes heart-rate
zones against the **resolved zone reference** (custom > manual max HR >
age-derived, from M13a) instead of only the profile's manual max heart rate —
and each result is stored as a versioned `activity_zone_snapshots` row.

**Decisions:**
- **Custom replaces percent bands.** A `custom` reference uses the explicit
  boundaries (`hr <= top1`, `(top1, top2]`, …, zone 5 above `top4`); a
  `max_heart_rate`/`age` reference keeps M12's percent-of-max-HR bands against
  that reference's max HR (for age, `220 - current_age`). No fallback: no
  reference → `heart_rate_zones: null` (unchanged from M12).
- **Reuse, then supersede.** Trackpoints are immutable and the bands depend
  only on trackpoints + reference, so a live snapshot whose recorded reference
  matches the resolved one is returned as-is (no re-aggregation of up to
  100k samples per view). A changed reference recomputes and **supersedes**:
  the old row is soft-deleted (kept for history) in the same transaction as the
  new insert — "one live row per activity" holds, and changing your profile
  still updates every activity immediately (M12's guarantee). "Match" means
  source + effective values (the custom tops, or the max HR; `age` is display
  metadata). An activity with no HR timeline gets neither zones nor a snapshot.

**Gates:** `make lint` green (ruff, mypy 101 api files, tsc, eslint) · `make
test` green (**242 passed** — +6 new in `TestZoneReferenceAndSnapshots`) · api
image rebuilt; live check passed (below). No schema change in this slice.

### Code
- `ActivityTrackpointDao` — the aggregation (lead-based per-sample gaps + sum
  FILTER) extracted to `_aggregate_zone_seconds(activity_id, zone)`; the percent
  bands stay `zone_seconds_for`, and a new `custom_zone_seconds_for(activity_id,
  tops)` builds the boundary bands. Same per-sample timing rule as before.
- `ActivityService` — `_zones_for` now: resolve the reference (`None` → no
  zones); reuse a matching live snapshot; else recompute via `_compute_zones`,
  then supersede + store (`_store_snapshot` commits). New
  `ActivityZoneSnapshotDao` injected (constructor + dependency wiring); the old
  "profile max HR only" path is gone. `_reference_matches` holds the match rule.
- New `ActivityZoneSnapshotMapper`: `create(activity_id, reference, stats)` (per-
  source field population) and `to_stats(snapshot)`.

### Tests (6 new, `TestZoneReferenceAndSnapshots` in `test_activities.py`)
- Age reference computes zones (dob only → zone 5 non-empty, proving the derived
  178 bpm drives the bands) + its snapshot records `source='age'`, the derived
  max HR, and the age.
- Custom boundaries replace percent bands (custom wins over a manual 200: zone 1
  non-empty where percent-of-200 would be empty; whole 1480 s distributed) + the
  snapshot records `source='custom'` and the tops, no effective max HR.
- Snapshot reuse + supersede: three views under one reference write exactly one
  row; changing the max HR writes a second, leaving **one live (new mhr) + one
  soft-deleted (old mhr)** row.
- No HR timeline → `null` zones and **no** snapshot row (inline no-HR GPX).
- Snapshots are scoped per activity (a second activity has its own row, never the
  first one's).

### Live check (api rebuilt on :9090)
Fresh smoke user, `run_sample.gpx` (HR 120–160 ramp): no profile → `null` ·
max HR 180 → `{z3:200, z4:300, z5:980}` (M12's exact numbers) · second view
reused it (no new row) · custom tops 150/152/154/160 → `{z1:620, z2:40,
z3:40, z4:780}` (custom bands) · clearing the custom set → back to max-HR-180
bands · date of birth only (max HR cleared) → `{z3:180, z4:280, z5:1020}` against
the age-derived 178 bpm. History for the activity: **four** rows, one live
(`source='age'`, mhr 178), three superseded. Health ok, version unchanged (0.3.0).

### Docs
`api.md`: detail-endpoint note rewritten for the zone reference + snapshot reuse;
profile section cross-references it · `data-model.md`: "Heart-rate zones"
section rewritten (custom vs percent bands, when snapshots are written/reused/
superseded) · `usage.md`: Heart-rate zones section now the three-way reference +
custom-boundary semantics; Profile bullet adjusted.

**Next: M13c — profile UI for date of birth + custom zone tops** (the API has
existed since M13a; the Profile page still only exposes max/resting HR).

## M13a — User-configurable heart-rate zones (I): settings, reference resolution, snapshot schema (2026-08-30)

First slice of M13. A user can now define *what* their heart-rate zones are
computed against — beyond M12's single "max heart rate" knob: a complete set of
four **custom zone boundaries**, or an **age-derived** max heart rate
(`220 - current_age`) from a date of birth. This slice lands the settings,
the fixed-precedence **reference resolution** (exposed in the profile view),
and the schema for versioned per-activity zone results — **no change to how
the detail endpoint computes zones yet** (still M12's view-time, max-HR-based;
feeding it the resolved reference + writing snapshots is M13b), and no UI for
the new settings (a later slice).

**Decisions:**
- Precedence is fixed and unambiguous: **custom zones > manual max heart rate
  > age-derived**. Custom counts only as a *complete, strictly-ascending set of
  four* (or all cleared) — validated in the service so clients get the app error
  envelope; a partial set stored cannot exist. Date of birth is validated to an
  implied age of 1–120 (plus a formula backstop in the resolver so `220 - age`
  can never go non-positive).
- A zone **snapshot** is one computation: it records the reference used (`source`
  + its values) *and* the resulting seconds per zone. At most one live row per
  activity (partial unique index on `activity_id WHERE deleted_at IS NULL`); a
  superseded row is soft-deleted and kept for history, never destroyed. Nothing
  writes snapshots yet (M13b); the table + DAO exist so that slice is code-only.

**Gates:** `make lint` green (ruff, mypy 100 api files, tsc, eslint) · `make
test` green (**236 passed, 0 xfail**; new in this slice: `test_zone_reference.py`
with the resolver's 12 unit tests, the snapshot DAO's 9 constraint/behavior
tests in `test_zone_snapshots_dao.py`, and the profile reference API cases in
`test_users.py`) · migration verified up/down/up on a fresh scratch DB
(`ht_m13a_verify`, dropped after) · live stack migrated in place, api image
rebuilt; live check passed (below).

### Migration
`20260830000001_zone_config_and_snapshots.sql` — `user_profiles` gains
`date_of_birth date NULL` + four optional custom zone tops (each `> 0 AND
<= 300`); new reference table `zone_sources` (seeded `custom` /
`max_heart_rate` / `age`, immutable) and `activity_zone_snapshots` (int id PK,
uuid FK → activities CASCADE, source FK + per-source reference values, five
zone-second columns, audit columns; partial unique index for "one live row per
activity"; `updated_at` trigger). Verified: fresh DB → up (all migrations) →
down 1 (both tables and all five profile columns gone, shape checked) → up
(re-applied), then scratch DB dropped.

### Code
- `app/services/zone_reference.py` — pure resolution: `ZoneReference` dataclass,
  `current_age(dob, today)`, `resolve_zone_reference(profile, today)` with the
  fixed precedence (unit-testable without a DB). `ZoneSource` StrEnum mirrors
  the reference table.
- Profile surface: `user_profiles` model + DAO apply gains date of birth and the
  four custom tops; `ProfileUpdateRequest` (bpm fields ge=30 le=300) and
  `ProfileView` gain the stored fields **plus computed** `zone_source`,
  `effective_max_heart_rate` and `age`. `UserService.update_profile` validates
  the resulting dob (not future, age 1–120) and custom set (complete +
  strictly ascending); `get_profile_view` resolves the reference.
- New `ActivityZoneSnapshot` model (+ registered in `app.models`) and
  `ActivityZoneSnapshotDao` (`get_current`, `add`, `mark_superseded`) — the
  write path M13b will use; unused by any service in this slice.

### Tests
- `test_zone_reference.py` (12, pure): age boundaries, each source alone,
  precedence custom > max HR > age, partial custom set ignored, resolver backstop
  for an implausible (non-positive formula) age.
- `test_zone_snapshots_dao.py` (9, against the migrated test DB — also proving
  the migration's constraints): round-trip; a second *live* snapshot for one
  activity is rejected by the partial unique index; an unknown `source` is
  rejected by the reference FK; supersede soft-deletes (row kept, `deleted_at`
  set) and frees the slot for a new snapshot; double-supersede is a no-op;
  per-source field population (custom tops vs max HR); user delete cascades away.
- `test_users.py` profile reference cases (added earlier in this slice): empty view shape,
  dob → `zone_source: age` with derived max HR + age, precedence custom over age
  and max-HR-over-age, null clears / omitted keeps, future dob 422, implausible
  dob 422, partial custom set 422, non-ascending set 422, full-set round-trip.

### Live check (api rebuilt on :9090)
Fresh smoke user: GET profile → all settings null, `zone_source` null · PATCH
dob `1984-05-01` → `zone_source: "age"`, `effective_max_heart_rate: 178`
(220 − 42), `age: 42` · PATCH a full custom set → `"custom"` (wins over age;
effective max HR null) · PATCH the four custom tops as explicit `null` → back to
`"age"` 178 · future dob → 422 `VALIDATION_ERROR` · partial custom set (two of
four) → 422. Health ok, version unchanged (0.3.0).

### Docs
`data-model.md`: `user_profiles` columns, new `zone_sources` +
`activity_zone_snapshots` table sections, "Heart-rate zones" section rewritten as
reference + view-time computation (noting M13a feeds only max HR into it), ER
diagram, migration row · `api.md`: profile GET/PATCH with the computed
zone-reference fields and the validation rules. No `usage.md` change (no UI yet).

**Next: M13b — feed the resolved reference into the detail computation and write
the versioned snapshots** (custom boundaries replace percent bands for custom;
age/max-HR keep the bands against their max HR).

## M12 — Heart-rate zones: profile-relative, computed at view time (2026-08-30)

Started from a bug report: the owner's only real activity ("Morning Run",
avg HR 112, max 129) showed ~83% of its time in **zone 5**. Investigation:
the stored zones were internally consistent with the import-time algorithm —
the algorithm's reference was the problem. With no profile max heart rate set
(the owner has no profile row), the code fell back to *the activity's own max
HR* (129), so 112 bpm = 87% → zone 5. A second latent flaw: zones were frozen
at import, so setting a max heart rate later would never fix old activities.

**Decision:** zones are relative to a *person*, so they are computed **at view
time** from the stored trackpoints, against the **viewer's current profile max
heart rate** — and there is **no fallback**. No profile max HR (or no HR
timeline) → `heart_rate_zones: null` and a UI hint linking to the profile,
instead of a misleading chart. The `activity_hr_zones` table is dropped.

**Gates:** `make lint` green (ruff, mypy, tsc, eslint) · `make test` green
(**205 passed, 0 xfail** — one import-time zone unit test removed, two
view-time API tests added) · migration up/down/up verified on a fresh scratch
DB · api + web images rebuilt; live check passed (below).

### Migration
`20260829000001_drop_activity_hr_zones.sql` — `up` drops the table; `down`
recreates it (columns, unique `activity_id`, trigger, comments) exactly as it
stood. Verified: fresh DB → up (all migrations) → down (table restored,
shape checked) → up (dropped again), then scratch DB removed.

### Code
- `ActivityStatistics.compute` no longer computes zones or takes a max HR;
  `compute_hr_zones`/`_zone_for` removed from the import path. `HrZoneStats`
  stays, now as the view-time result type.
- `ActivityTrackpointDao.zone_seconds_for(activity_id, max_heart_rate)` —
  one SQL aggregation over the stored trackpoints: `lead()`-based per-sample
  gaps, percent-of-max-HR `case` bands, `sum() FILTER` per zone; `None` when
  there is no HR timeline. Same rules as before (each timed HR sample counts
  until the next).
- `ActivityService.get_detail` resolves the caller's profile max HR and calls
  the DAO (constructor now takes `UserProfileDao` instead of the zone DAO).
- `ImportService` loses the profile + zone DAOs entirely — import stores
  nothing zone-related.
- `ActivityMapper.to_detail_view` takes `HrZoneStats | None`;
  `create_hr_zones` removed. `ActivityHrZone` model +
  `ActivityHrZoneDao` deleted.
- UI: when zones are `null` but the activity has HR trackpoints, the zones
  card explains why and links to the Profile page.

### Tests
- `test_imports_gpx_run` now expects `heart_rate_zones: null` at import time
  (no profile max HR).
- New `TestHeartRateZonesViewTime`: no profile max HR → zones `null` despite
  HR data · set max HR 180 → zones appear (zone 1 empty, zone 5 > 0) · change
  to 200 **without re-import** → the distribution shifts (160 bpm is 89% of
  180 → zone 5, but exactly 80% of 200 → zone 4, so zone 5 empties). This
  last step is the regression the bug report was about.

### Live check (api + web rebuilt on :9090)
Fresh `m12-smoke` user: uploaded `run_sample.gpx` (HR 120–160) → zones `null`
· `PATCH /users/me/profile` max 180 → zones `{z3: 200, z4: 300, z5: 980}`
(sum = full 1480 s) · max 200, same activity, no re-import → `{z2: 160,
z3: 320, z4: 1000, z5: 0}`. The owner's real activity (no profile max HR
set) now returns `null` zones; against a plausible 190 bpm its trackpoints
distribute mostly into zone 2 — matching the avg-112 effort, instead of the
old 83%-zone-5.

### Docs
`data-model.md`: zones section rewritten as computed-not-stored, ER diagram +
`user_profiles` notes, migration table row · `api.md`: detail-endpoint note
on view-time, caller-relative zones · `usage.md`: Heart-rate zones section
rewritten (no fallback, changes apply everywhere immediately, profile hint).

## M11e — Sync lookback: the floor bounds the walk, per-run `since` (2026-08-29)

Fifth and final slice of M11 (and of the self-serve Strava effort as a whole):
the import-from floor is now the sync walk's lower boundary, and a one-off
`since` overrides it per run.

**Gates:** `make lint` green (ruff, mypy, tsc, eslint) · `make test` green
(**204 passed, 0 xfail** — the M11e contract stub came off and is a real test
again) · api + web images rebuilt; live check passed (below).

### The floor is the walk's only boundary
- Precedence per run: the request's `since` (UTC midnight) → the
  connection's saved `sync_since` → no floor (full history). The chosen floor
  is sent as the provider list call's `start_date` on **every** page, so a
  paused/resumed run keeps walking the same range.
- The provider stops returning rows once the walk crosses the floor, so a
  floored walk ends on a short page and clears its cursor like any completed
  walk. Dedup (already-imported ids are skipped, no detail re-fetch) is
  unchanged.

### Code
- `ProviderAdapter.fetch_activity_ids` gains a keyword `start_date` (unix
  lower bound); `StravaClient.list_activity_summaries` sends it as
  Strava's `start_date` param.
- `ProviderSyncService.sync(user, provider, since=None)` resolves the floor
  (`_floor_to_unix`) and threads it through the walk; it is logged.
- `POST /providers/{p}/sync` accepts an optional body
  `{"since": "YYYY-MM-DD"}` (`SyncRequest`); no body = saved floor or none.
- UI: a **Rescan from…** control on the connected row (one-off date + run)
  beside Sync; the floor control from M11d persists the standing preference.

### Tests (7 new in `TestSyncLookback`; the xfail contract file was folded in)
`since` imports only activities at/after it (the former xfail contract, now
real) · the saved floor bounds the walk with no request · request `since`
overrides the saved floor (and leaves it untouched) · the floor is sent on
every list call · a two-page floored walk pages past a full page, fetches the
empty tail, and completes (cursor cleared) · malformed `since` 422s.
`MockStravaSince` was merged into the shared `MockStrava` (which now honors
`start_date` and records list params), per the stub's note; the xfail stub
file was deleted.

### Live check (api + web rebuilt on :9090)
Health ok · `POST /sync` without a body → 404 (unconfigured; no regression) ·
`POST /sync` with a `since` body → 404 (body parses, same downstream) ·
malformed `since` → 422 · SPA serves the new bundle.

### Docs
`api.md`: the sync endpoint's optional `since` body and floor precedence ·
`usage.md`: "Rescan from…" under Connected accounts.

**M11 is complete** (M11a–M11e): the deployment's Strava client is entered in
the app, stored encrypted, live without a restart; users connect their own
accounts, choose an import-from floor, and can rescan any range one-off.

## M11d — Server settings UI + import-from floor (2026-08-29)

Fourth slice of M11: the frontend for self-serve provider configuration, plus
the per-connection import-from floor (stored and settable; the sync walk
honoring it is M11e).

**Gates:** `make lint` green (ruff, mypy, tsc, eslint) · `make test` green
(198 passed: 191 pre-existing + 7 new connection-settings tests; 1 xfail =
the M11e lookback stub) · api + web images rebuilt; live smoke passed (below).

### Server settings page
New `/settings` page ("Server settings" in the nav and the title). The
Providers section (the M11 scope) shows one card per provider with a
Configured/Not-configured badge, a Client ID field, a Client secret password
field ("Leave blank to keep the current secret" once configured — the secret
can never be read back), an optional Display name, Save, and Remove (confirm
warns that existing connections pause). Any signed-in account may use it (the
homelab assumption, Q6).

### Connection states on the Profile page
- Provider not configured, no connection → "Not configured on this server." +
  a link to Server settings.
- Provider not configured but a connection exists (orphan, Q10) → "Sync
  paused — … is not configured on this server." + a re-add link; no
  Sync/Disconnect buttons (both 404 without a registry adapter).
- Configured + connected → the row gains an **Import from** control: presets
  (All time / 30 days / 90 days / 1 year) plus a custom date input, persisted
  immediately.

### Import-from floor (API side)
`provider_accounts.sync_since` (M11a) is now settable:
`PATCH /providers/{p}/connection {"sync_since": "YYYY-MM-DD"|null}` — stored
as UTC midnight; the connection view now returns `sync_since`. It is a user
preference: it survives reconnects (`apply_credentials` deliberately does not
touch it). 404 when there is no connection (or the provider is unknown); 422
for a malformed date.

### Tests (7 new, `TestConnectionSettings` in `test_providers_api.py`)
Set the floor and read it back (stored at UTC midnight) · null clears it ·
the floor survives disconnect + reconnect · no connection 404s · unknown
provider 404s · malformed date 422s · unauthenticated 401s. The callback
test's exact key-set assertion now includes `sync_since`.

### Live smoke (api + web rebuilt on :9090)
Health ok · SPA served at `/settings` · PATCH without a connection → 404 ·
seeded a connection row → GET `sync_since: null` → PATCH stores
`2026-06-01T00:00:00Z` and reads it back → PATCH null clears it → malformed
date 422s (seed row cleaned up afterwards).

### Docs
`usage.md`: new "Server settings" section + the floor in Connected accounts
(also fixed the "server administrator" wording — any account configures) ·
`api.md`: `PATCH …/connection` + `sync_since` on the connection view + a
sync-section note that the floor bounds imports (enforced in M11e).

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
