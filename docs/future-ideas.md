# Future ideas

Ideas parked here are not scheduled. Each entry records when it was parked,
why it is interesting, and — where known — a feasibility sketch, so the idea
can be picked up later without re-research.

## Import duplicate detection with user-confirmed overwrite (parked 2026-09-09)

If a newly imported activity (file upload *or* provider fetch) is an **exact
duplicate** of one the user already has, ask: overwrite it (soft-delete the old
row and insert the new one — chronological position is automatic, since the feed
orders by `started_at`) or keep both? For a bulk provider sync, confirming many
potential duplicates is a UX nightmare — there the user gets **one choice for
the run**: ignore duplicates (today's behavior) or overwrite every match.

Current state, per source:
- **File uploads**: no dedup at all — re-uploading the same file (or a second
  export of one workout) silently adds another row; duplicates accumulate in the
  feed and pollute dashboard stats (M18).
- **Provider sync**: always ignores — `exists_for_provider(provider,
  external_activity_id)` skips re-delivered ids (reported as the `skipped` count).

Feasibility sketch — open questions to settle when scheduled:
- **"Exact duplicate" for files** has no external id; candidates are a hash of
  the original bytes (fragile across formats — GPX vs FIT exports of one workout
  differ) or a field tuple (`sport_type`, `started_at`, `duration_seconds`,
  `distance_m`) (format-robust, but collides on genuinely identical workouts). A
  confirm dialog showing both activities side by side lets a human make the call.
- **Two-phase import**: parse → check against the user's active activities → ask
  before committing (no post-hoc cleanup).
- **Schema landmine**: the partial unique index on `(provider, external_activity_id)`
  is *not* soft-delete-aware (and `exists_for_provider` deliberately ignores
  `deleted_at`) — "soft-delete + re-import" of a provider activity would violate
  it today. Overwrite needs the index made soft-delete-aware (a migration) or an
  in-place replacement of the row.
- **Sync API/UI**: a per-run option, e.g. `POST /providers/{p}/sync
  {"on_duplicate": "ignore" | "overwrite"}` (default = today's ignore); the sync
  result view gains a `replaced` count; the control lives on the Profile
  connection row.
- Distinct from "Cross-provider duplicate activity detection" (heuristic matching
  of the same workout arriving via *different* providers) — this one is exact,
  within a source. Cross-reference both when scheduling either.
- Bonus fit: re-importing after a parser fix (e.g. M20's Hydrow distance) becomes
  first-class UX instead of "delete + re-upload".

## ~~Per-user frontend themes, dark mode first~~ — shipped as M25 (2026-09-13)

`ui_themes` reference table + `user_profiles.theme`; the palette is semantic
tokens redefined under a `.dark` class on `<html>` (pre-paint script, no
flash); `ThemeProvider` mirrors the units/timezone contexts and resolves
"system" via a live `matchMedia` listener; recharts take explicit dark values
(SVG attributes don't resolve CSS variables) and the route map swaps to a CARTO
dark basemap. Light / dark / system are all in v1; see `docs/progress.md`
(M25a–M25b) and the *Theme* section in `docs/usage.md`. Remaining: accent-color
theming — later, if ever.

## Activity images: Strava photo fetch (parked 2026-09-08)

Companion to the user-upload half, which **shipped as M22**
(`activity_images` + `image_sources`, gallery on the detail page; see
`docs/progress.md`). When pulling an activity from Strava, also fetch its
photos and store them locally (provenance `strava` — the value to add to
`image_sources`, into the reserved `source_url`).

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

## ~~Reach profile settings by clicking the user name~~ — shipped as M27 (2026-09-14)

The **Profile** nav item is gone; the user's name in the header (right side,
always visible now) *is* the link to `/profile`, with hover and active affordance.
It doubles as "account menu" later if more personal actions appear (see the live
stack's header or `web/src/components/Layout.tsx`).

## User location (parked 2026-08-30; the timezone half shipped in M23)

Let the user set a **location** (city/state and/or coordinates) in their
profile. The sibling idea — an IANA **timezone** for display — is done: M23
stored `user_profiles.timezone` (zoneinfo-validated) and the client now renders
day-grouping, dates/clocks and dashboard period boundaries in that zone (null =
browser local).

What remains: a free-form `location` column on the same profile, plus
everything that would consume it —

- user-localized weather (see "Weather along an activity") and any future
  scheduled/reminder features need a *place*, not just a zone;
- an optional location on the dashboard ("12 km run in Berlin") or weather
  lookups by coordinate.

Nothing to consume it yet, so it stays parked; the M23 profile surface (field +
validation + context) is already there to extend.

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

- Related: "Import duplicate detection with user-confirmed overwrite" (parked
  2026-09-09) — exact duplicates within a single source, with an overwrite
  option; this entry stays about cross-provider heuristic matching.

## Weather backfill across a user's library (parked 2026-09-13)

Companion to "Weather along an activity" (shipped as M24): fetch snapshots for
**all** of the user's outdoor activities in one go, instead of waiting until
each detail page is opened. Parked deliberately — bulk-fetching a library the
user may never look at contradicts M24's strictly-on-demand, offline-capable
spirit; it becomes interesting once the user actually wants weather on many old
activities.

Feasibility (verified while scoping M24): the same Open-Meteo Historical
Forecast API covers hourly data back to ~2021 (ERA5 archive, ≈25 km cells,
covers 1940+ for deep history), keyless at a 10k calls/day rate limit —
thousands of activities backfill in a day or two. Everything M24 built is
reusable: the client, `fetch_or_cached` per activity (a backfill loop just
calls it and skips cached rows, which also makes the run **incremental and
resumable**), the 422 for no-GPS activities (skip), and `WEATHER_ERROR`
per-activity failures (report, continue). A per-user `POST /weather/backfill`
(or a batch endpoint with progress) plus a "Fetch weather for all my
activities" button on the dashboard would be the shape; pre-2021 activities
need an explicit "no data" outcome rather than an error.

## ~~Weather along an activity~~ — shipped as M24 (2026-09-13)

Opt-in per-activity weather from Open-Meteo (keyless, CC BY 4.0): start/end
condition chips + a temperature-over-time curve for longer efforts, cached per
activity (`activity_weather`), GPS-only activities. See `docs/progress.md`
(M24a–M24c) and the *Weather* bullet in `docs/usage.md`; the remaining half —
bulk backfill across a library — is parked above.

<details><summary>Original research (kept for the backfill idea)</summary>

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

</details>
