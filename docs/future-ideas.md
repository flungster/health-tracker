# Future ideas

Ideas parked here are not scheduled. Each entry records when it was parked,
why it is interesting, and — where known — a feasibility sketch, so the idea
can be picked up later without re-research.

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
