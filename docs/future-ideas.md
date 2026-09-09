# Future ideas

Ideas parked here are not scheduled. Each entry records when it was parked,
why it is interesting, and — where known — a feasibility sketch, so the idea
can be picked up later without re-research.

## Rowing: distance rowed as a first-class metric (parked 2026-09-08)

The rowing detail card shows stroke rate and the 500 m split, but distance only
appears in the generic stat grid shared by all sports. Surface "distance rowed"
on the **Rowing** card itself (unit-aware via M14, like walking's pace in
M16), and optionally on feed cards.

- `activities.distance_m` is already stored for rowing (GPX and Strava both
  provide it) — **no DB change**.
- Sketch: render the detail-level `distance` inside `RowingDetail`, or add a
  card-local field to the rowing metrics view — decide when scheduled. Trivial;
  proposed for a small polish milestone alongside "Strava setup instructions in
  the Server Settings" (below).

## Per-user frontend themes, dark mode first (parked 2026-09-08)

Let the user pick a UI theme; **dark mode** is the obvious first one. It is
user-configurable, so — like the units setting (M14) — it lives in the DB
per user, not client-only.

- **Storage**: a theme is multi-valued (light / dark, possibly "system"), so
  the reference-table rule applies: `ui_themes` (PK value + description, seeded
  immutable) + `user_profiles.theme text NULL` FK; NULL = the app default. (The
  M14 timestamp trick does not apply — it was a two-state setting.)
- **Frontend**: `web/src/index.css` defines the palette as a small set of
  semantic tokens (`canvas`, `surface`, `ink*`, `line`, accent, …) in a
  Tailwind v4 `@theme` block and every component uses those tokens — so dark
  mode is **redefining ~10 token values under a `.dark` class** (Tailwind v4
  `@custom-variant dark`), not a component-by-component sweep. The real work:
  hardcoded colors in the recharts charts and Leaflet map tiles (light/dark
  tile layers).
- A theme context mirroring `UnitsProvider`: seed from localStorage pre-paint
  (no wrong-theme flash before the profile loads), then sync to the profile;
  `PATCH /users/me/profile` gains a field.
- Scope decisions for scheduling: include "system" (follow the OS, via a
  `matchMedia` listener) in v1? Accent-color theming — later, if ever.

## Activity images: user uploads (local-first) (parked 2026-09-08)

Let users attach photos to their activities (most Strava workouts have
pictures). This half is deliberately **provider-free**: it works with zero
connected accounts and keeps the app local-first — images are stored locally
and never leave the server.

- **Storage**: files under `uploads/<user_id>/images/` (mirroring the import
  file layout); new table `activity_images`: int id PK + uuid, FK →
  `activities.uuid` (CASCADE), a provenance column (`uploaded` vs `strava`,
  reference table per the enum rule), original filename / source URL when from
  a provider, standard audit columns; soft delete.
- **API**: list/serve per activity (served locally), multipart upload, delete;
  reuse the existing `MAX_UPLOAD_MB` limit and file-serving pattern.
- **UI**: a gallery on the activity detail page + an add-photo action.

## Activity images: Strava photo fetch (parked 2026-09-08)

Companion to the upload idea above: when pulling an activity from Strava, also
fetch its photos and store them locally (provenance `strava`).

- **Research gate — unverified**: the Strava v3 activity JSON exposes
  `photo_count` and a thumbnail URL (`small_callback_url`), but there is no
  known *official* public endpoint that downloads **all** photos of an activity
  (the web UI's full photo list appears to use internal endpoints). Verify what
  the API actually offers before committing.
- If only a thumbnail is available: decide whether one cover image per activity
  is worth the plumbing, or drop this half entirely and let users upload.
- Fits the provider rules either way (read-only, the connected user's own
  activities); opt-in on demand like weather, or at sync time — decide when
  scheduled.

## Strava setup instructions in the Server Settings (parked 2026-09-06)

The provider client card on the **Server settings** page
(`web/src/pages/SettingsPage.tsx`, `ProviderConfigCard`) asks for a **Client ID**
and **Client Secret** but gives no hint where they come from — the operator has
to already know Strava's API portal.

Add per-provider setup help to the card (a "How do I get these?" block or a link
to a docs section) covering, for Strava:

1. Create an application at `https://www.strava.com/settings/api` (select
   "Read" scope / non-elevated for this use).
2. Copy the **Client ID** and **Client Secret** from that page into the card
   (the secret is stored encrypted and never shown again — same rule as today).
3. Add this server's OAuth callback URL,
   `https://<host>/api/v1/providers/strava/oauth/callback`, to the app's
   **Redirect URIs** (the callback route is `api/app/http/providers.py:63`).

Sketch: a short collapsible help block rendered per provider value (the text is
provider-specific; only Strava exists today), or a pointer into `docs/usage.md`
if the prose grows too long for the card. Trivial change; parked because it is
cosmetic and not part of the current milestone scope (M15 — rowing).

## Reach profile settings by clicking the user name (parked 2026-08-30)

The nav bar shows the signed-in user's first name (`web/src/components/
Layout.tsx`) *and* a standalone **Profile** nav link. The profile is personal,
so the name itself should be the entry point: drop the **Profile** nav item and
make `{user.first_name}` a link to `/profile` (with hover affordance). The name
doubles as "account menu" later if more personal actions appear.

Trivial change; parked because it is cosmetic and not part of the current
milestone scope.

## User location + timezone (parked 2026-08-30)

Let the user set a **location** (city/state and/or an IANA timezone, e.g.
`Europe/Berlin`) in their profile, and render activity times **relative to that
timezone** instead of the browser's local timezone.

- Today, all dates/times are stored UTC and the SPA renders them in the
  *client's* local timezone (feed day-grouping "Today / Yesterday" uses the
  client-local date of `started_at`). A user who travels or runs the homelab UI
  from a different machine sees their day boundaries shift.
- With a stored timezone, the API/UI could return per-user-localized dates (or
  send `tz` to the client and localize in one place), making day-grouping,
  start times, and any "today" logic stable for that user.
- Fits naturally in `user_profiles` (a `timezone text NULL`, optionally a free-
  form `location text`); validation against IANA names (the `tzdata` database —
  Python's `zoneinfo`). Client-side, a small tz-aware date helper.
- Also the prerequisite for user-localized weather (see "Weather along an
  activity") and any future scheduled/reminder features.

## Cross-provider duplicate activity detection (parked 2026-08-30)

When a user connects **multiple providers** (e.g. Garmin and Strava), the same
workout can arrive from both, producing two local activities for one effort.

Today only *within-provider* dedup exists: `activities` has a partial unique
index on `(user_id, provider, external_activity_id)`, so the same external id
from the same provider imports at most once. Across providers there is no
dedup and no detection — both rows are kept silently.

### Why it is a real problem (and not trivial)
- No shared external id across providers. A run's Strava id and Garmin
  activity number are unrelated.
- Matching has to be heuristic: same sport, overlapping time window (within a
  small tolerance), similar distance/duration. GPS overlap would be the
  strongest signal but trackpoints are heavy to compare.
- The right UX is "detect and let the user decide" (flag likely dupes, merge
  or dismiss), not silent auto-merge — a wrong guess destroys data.

### Sketch of how it would fit (refine when scheduled)
- A dupe-scan that groups the user's activities by sport + time window
  (e.g. starts within N minutes of each other, similar duration), then scores
  pairs by distance/duration/HR similarity (GPS overlap optional).
- Surface candidates in the UI ("These two look like the same run — keep both
  / delete one"); user confirms, nothing is auto-deleted.
- Only becomes necessary once a second provider (Garmin) ships; with Strava
  alone there is nothing to cross-match.

## Weather along an activity (parked 2026-08-29)

For each **outdoor** activity, show what the weather was like at the time and
how it changed over the course of the activity:

- conditions during the activity (sunny / partly cloudy / overcast, rain)
- humidity and dew point
- apparent ("feels-like") temperature
- **temperature over time** — the differentiator: the temperature traced
  along the activity's duration, most useful for multi-hour efforts (long
  runs, long rides). For sub-hour activities, start + end conditions are
  enough.

Indoor sports (strength, indoor rowing, yoga, …) are assumed
climate-controlled and get nothing.

### Feasibility: yes — researched 2026-08-29

Open-Meteo (https://open-meteo.com) provides exactly this, with **no account
and no API key for non-commercial use**:

- **Historical Forecast API** (`historical-forecast-api.open-meteo.com`) —
  a continuous hourly global timeseries stitched from archived model runs
  ("Best Match": ECMWF IFS 9 km, NCEP GFS/HRRR 3 km in the US, …), back to
  ~2021 (per-model back to 2017). One GET returns, per hour:
  `temperature_2m`, `apparent_temperature`, `relative_humidity_2m`,
  `dew_point_2m`, `weather_code` (WMO: clear / mainly clear / partly cloudy
  / overcast / fog / drizzle / rain / snow / showers / thunder),
  `precipitation`, cloud cover (total + low/mid/high), wind, UV index.
- Verified live (sample call, Seattle, 2026-08-15): all of the above came
  back for the day, including the daytime temperature curve.
- **Historical Weather API** (ERA5 reanalysis, 0.25°, from 1940) covers deep
  history where the forecast archive has no data.
- 15-minute resolution is available for Central Europe and North America.
- No client library needed: plain HTTPS GET → JSON; `httpx` is already a
  dependency. The rate limit (10k calls/day) is irrelevant at homelab scale —
  a fetch is one call per activity.
- Non-commercial use requires attribution (data is CC BY 4.0).

### Sketch of how it would fit (refine when scheduled)

- Strictly **opt-in**, in the spirit of the provider rule: nothing is
  fetched at import time; the activity detail page gets a "Show weather"
  action for outdoor activities that carry GPS, and the app stays fully
  functional offline.
- Backend: resolve the activity's location (start point / route centroid),
  fetch the hour range `started_at..ended_at`, cache the snapshot in a table
  keyed by activity — re-opening the page never re-fetches.
- UI: start/end condition chips (condition + temp / feels-like / humidity /
  dew point) and, for longer activities, a temperature-over-time line
  aligned to the activity's duration (recharts already draws HR this way).
- Accuracy note: this is model/grid data (~9–13 km cells), not a station
  reading — an acceptable trade for this use.
