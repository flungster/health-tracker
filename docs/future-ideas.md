# Future ideas

Ideas parked here are not scheduled. Each entry records when it was parked,
why it is interesting, and — where known — a feasibility sketch, so the idea
can be picked up later without re-research.

## Research batch — 2026-10-10 (ideas, not commitments)

A research pass over the self-hosted fitness landscape and this repo's
stored data, asked for *additional* product ideas. The entries below are
**ideas only**: nothing here is scheduled, scoped for a milestone, or
committed to. Some will be parked individually (with the usual
when-parked / why / feasibility sketch) when one earns it; most may stay
brainstorm forever. They are grouped by how they relate to what already
exists, and each notes the existing code it would build on.

### Compute harder on data already stored (fully offline, no new sources)

- **Training load / fitness–fatigue–form (PMC)** — daily CTL/ATL/TSB curves
  over a range, the "Performance Management Chart" every endurance app has.
  Derive per-activity load (TSS from power, or TRIMP-style HR+duration) out
  of `activity_trackpoints` + activity columns, sum per calendar day (the
  dashboard already groups by day), run a recursive EWMA (τ=42/7). Pure and
  offline, view-time — mirrors the zone-snapshot pattern (one live row per
  activity or a daily-load table). A companion idea: **cardio/effort
  decoupling** within long efforts (does pace/power climb while HR climbs?)
  from the same streams. The marquee Tier-1 candidate: high perceived value,
  no new data needed.
- **Best efforts / personal records** — auto-detect PRs: fastest 5k/10K/half
  from the precomputed `activity_splits` (any x-km window), max power / n-min
  effort from trackpoints, longest distance/duration. A "PRs" card plus a
  badge on the feed when an import sets one. PR detection is a scan at
  import or view time; cheap and sticky.
- **Route & climb analysis** — climb detection (longest climb, average/peak
  gradient), punchiness score, per-route elevation profile and comparison of
  repeated routes. Pure derived metrics over `trackpoints.altitude_m`; same
  shape as the splits/zone modules.

### New local data sources (expands what "the platform" holds)

- **Apple Health import (`export.zip`)** — already a stated stretch goal in
  `AGENTS.md`, and the biggest strategic unlock here: it is a purely local,
  offline gateway (the user exports from their phone; no cloud provider) to
  **non-activity wellness data** — sleep, resting HR, body weight — in the
  same store. Without some wellness source (this or manual/CSV entry), the
  readiness idea below has nothing to read.
- **Finish manual strength entry** — `strength_exercise_sets` exists in the
  schema but (per the data model doc) nothing populates it yet. An exercise
  library + set/rep/rest form would complete a sport that is currently
  import-only, and feeds volume goals.

### Platform & integration layer (matches the "platform" framing)

- **Local AI coach / MCP server** — expose this local data through an MCP
  endpoint so a locally-run LLM (the owner already runs LM Studio) can answer
  questions over the user's own history, plus a generated daily/weekly review.
  This is becoming table stakes in the self-hosted competitor set and fits the
  privacy-first thesis: no data ever leaves the box. Decide scope (read-only
  recall vs write actions) before anything else; note Strava's API terms keep
  provider-sourced data out of AI context by default in comparable projects.
- **A second provider (Garmin Connect or intervals.icu)** — the parked
  GPS-overlap and cross-provider dedup entries both say they only get good
  once a second adapter ships; adding one unlocks that already-built,
  provider-agnostic dedup path and (via intervals.icu) a wellness feed as well.
  Heavier than the ideas above because it means real OAuth + sync work, not
  just local computation.
- **Recovery / readiness dashboard** — a daily "ready vs loaded" score from the
  user's own baselines (resting HR, sleep) combined with Tier-1 training load.
  **Depends on a wellness source** (Apple Health import or manual/CSV entry) —
  parked here as the consumer side of that dependency.
- **Goals & targets** — weekly/monthly distance/volume/calorie/zone-time goals
  that auto-update as activities land; progress per period plus historical
  attainment. A natural extension of the existing dashboard period-stats API.

### Cheap wins (small, quick visual value)

- **Calendar heatmap / streaks** — a contribution-style grid of activity
  counts/intensity by day, plus per-sport streaks; the dashboard already does
  the day grouping. Mostly a render feature.
- **Export / portability** — one-click CSV/JSON (and GPX re-export where
  trackpoints exist) of the user's activities, splits and PRs. Purely on-thesis
  ("the data is yours") given the views layer already exists.
- **Library health report** — a "what's missing" view: activities without GPS,
  HR or weather snapshots. Doubles as the entry point for the already-parked
  weather-backfill idea and any future backfills.

## ~~Import duplicate detection with user-confirmed overwrite~~ — shipped as M28 (2026-09-14)

Shipped with a twist the sketch had anticipated: instead of silently
overwriting, a match **links** — `activities.duplicate_of` self-FK (depth ≤ 1).
The primary stays live in feeds/counts/dashboards; the duplicate is kept, still
reachable by its own id, hidden from list-style reads. Everything reversible:
unlink or promote (swap), and overwrite (`POST /activities/{id}/duplicates/overwrite`)
soft-deletes the replaced row like any delete — no data loss, rollback kept.

- **Detection** (pure module `app/services/duplicate_detection.py`): same sport,
  start within 30 minutes as UTC instants (never wall-clock — parse-time TZ bugs
  are the real risk), duration within max(60 s, 5%) or distance (when both rows
  have one) within ~10%. Conservative on purpose: a false positive hides an activity.
- **Uploads** prompt (confirm card after import, strongest match preselected);
  **bulk provider sync never prompts** — it links and reports via the new
  `SyncResultView.linked_duplicates` (safe: linking is reversible).
- The provider dedup index is now **soft-delete-aware** (the schema landmine in
  the sketch), so delete + re-import of a provider activity inserts fresh.

Still open from the sketch:
- **GPS trackpoint overlap** as a confidence booster (and for surfacing "these
  two routes match" in the UI) — trackpoint comparison is heavy; revisit when a
  second provider ships.
- **In-place overwrite action in the UI** — the API endpoint exists (used by a
  confirmed re-import of one source's own activity); no button for it yet. The
  link/keep-both flow covers the common case non-destructively today.

## ~~Per-user frontend themes, dark mode first~~ — shipped as M25 (2026-09-13)

`ui_themes` reference table + `user_profiles.theme`; the palette is semantic
tokens redefined under a `.dark` class on `<html>` (pre-paint script, no
flash); `ThemeProvider` mirrors the units/timezone contexts and resolves
"system" via a live `matchMedia` listener; recharts take explicit dark values
(SVG attributes don't resolve CSS variables) and the route map swaps to a CARTO
dark basemap. Light / dark / system are all in v1; see `docs/progress.md`
(M25a–M25b) and the *Theme* section in `docs/usage.md`. Remaining: accent-color
theming — later, if ever.

## Automatic provider sync (scheduled background pulls) — parked 2026-10-10

Today, provider sync is strictly on-demand: the user taps "Sync" and
`POST /api/v1/providers/{provider}/sync` runs a walk. The idea: a background
worker (or job) that, **every X hours — configurable**, walks each user's
connected providers and imports whatever is new, so a connected account fills
itself in without the user ever touching it.

- **Everything is already there except a trigger.** M10d's sync walk (paged,
  cursor-resumable, token-refreshing), M11e's import-from floor + per-run
  `since` rescan, and M28a's auto-link on sync import all exist; a scheduled
  run is `ProviderSyncService.sync(user_uuid, provider)` with no body. The
  work is scheduling + surfacing, not new sync logic.
- **Shape:** a scheduler loop in the API process (e.g. APScheduler started at
  app startup — no new service, keeps the compose file untouched) that fires a
  sync per connected `provider_accounts` row. Interval is config: global env
  (`SYNC_INTERVAL_HOURS`, default e.g. 6, `0`/unset = off) with an optional
  per-user override on the profile later. Stagger runs (a few-second jitter)
  so a fleet of users doesn't hit Strava in lockstep.
- **Opt-in, per the provider rules.** Strictly local-first: nothing happens
  unless a user has connected an account, and the interval is configurable (and
  disable-able). The existing per-provider token refresh already keeps silent,
  background calls healthy.
- **Concurrency guard:** one in-flight sync per (user, provider) — skip the
  tick if a manual or previous scheduled run is still walking; track last-run +
  outcome so the UI can show "last synced Xh ago / N new".
- **Open question:** in-process loop vs. a separate worker container (the latter
  isolates long walks from the web process but adds a compose service + shared-DB
  coordination). Decide at scheduling time; the in-process loop is the smaller step.

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

## ~~Cross-provider duplicate activity detection~~ — shipped as M28 (2026-09-14, cross-source half)

The premise — "only becomes necessary once a second provider ships" — turned
out to be wrong: file ↔ provider is *already* cross-source (an uploaded GPX of
a run that also sits in the Strava feed), and M28 detects exactly that: same
matcher, candidates surfaced after an upload (confirm) or auto-linked during a
bulk sync. Provider ↔ provider will work the moment a second adapter ships — no
new core needed, since matching lives on plain signals (sport / start instant /
duration / distance) and the candidates query is provider-agnostic.

Remaining: **GPS-overlap scoring** (strongest signal, heaviest cost — see the
other entry). The **library-wide dupe scan** half shipped as M29 (2026-10-20):
`POST /activities/duplicate-scan` reports clusters across the caller's whole
library (same matcher, transitive groups), with a scan card on the Activities
page — report-only; nothing is ever auto-linked.

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
