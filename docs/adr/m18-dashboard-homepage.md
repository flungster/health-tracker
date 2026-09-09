# ADR: M18 — Dashboard homepage with period stats

Status: accepted (grilled 2026-09-08)
Milestone: M18

## Context

The app opens on the chronological activity feed (`/`). The owner wants a
logged-in homepage that answers "what did I do this day / week / month / year?"
at a glance — a snapshot, not a report. Clicking the `health-tracker` brand in
the top-left goes to this dashboard; clicking **Activities** shows the
chronological feed (descending by time).

## Decisions

### Routing and navigation

- New **Dashboard** page at `/`; the existing feed component moves to
  `/activities` (behavior unchanged: `started_at` descending, day-grouped).
- The brand in the header (`web/src/components/Layout.tsx`, a plain `<span>`)
  becomes clickable → `/`. The **Activities** nav item points at `/activities`
  (it currently targets `/`).
- Post-login/register already `navigate("/")`, so they land on the dashboard
  for free — no change.

### Period model

- **Current period only**, four fixed segments: Day / Week / Month / Year.
  No browsing past periods in v1 — a reporting UI is explicitly deferred; the
  API takes explicit instants, so adding navigation later is UI-only.
- **Week = Monday–Sunday**, fixed for now; open to making the week start
  configurable later.
- The selection is **client-side only** (URL param + localStorage memory): no
  DB column, unlike the units setting. Units went to the profile because the
  *API* needs it for conversion; a period choice is pure display state — the
  client computes `[start, end)` and sends instants.
- Period boundaries are computed in the **client's local timezone** (consistent
  with the feed's Today/Yesterday grouping). User-localized boundaries belong to
  the later "User location + timezone" idea.

### Stats (seven cards)

1. Activity count, with per-sport-type breakdown chips
2. Total moving time (`moving_seconds`)
3. Distance (unit-aware, M14)
4. Elevation gained (`elevation_gain_m`, unit-aware: m / ft)
5. Calories (kcal — never converted, per M14 rules)
6. Average heart rate = **simple mean of the per-activity averages**, over
   activities that have HR data (explainable: "the average of your
   activities' average HR"; time-weighting deferred)
7. Weight lifted = **sum of `strength_activity.total_weight_kg`** (total volume
   across the period's strength sessions — same semantics as the existing
   "Total volume" card), kg / lb per units

- **Steps are excluded**: no parser writes step counts today (GPX/TCX/FIT don't
  carry them; Strava doesn't return them) — the stat would be permanently "—".
- Streaks, per-sport PRs: deferred.

### Chart (one)

**Distance over time**, the only chart in v1 — it is what makes Week/Month/Year
feel like a dashboard. Bucket size adapts to the period: week and month → per
day; year → per month. The chart is **hidden in the Day view** (it degenerates
to one point). Unit-aware axis labels reuse the existing format helpers. No
metric switcher (calories/HR trends later, if ever).

### API contract

`GET /api/v1/activities/summary?start=2026-09-07T00:00:00Z&end=2026-09-14T00:00:00Z`

- Explicit UTC instants; **half-open `[start, end)`**; 422 on malformed or
  inverted ranges. Scoped by `user_id` as every other query (DAO rule).

Response:

```json
{ "units": "metric",
  "activity_count": { "total": 12, "by_sport_type": {"running": 5} },
  "moving_seconds_total": 91234,
  "distance": 61.208,
  "elevation_gain": 430.5,
  "calories_kcal": 8123.4,
  "avg_heart_rate_bpm": 137,
  "weight_lifted": 2719.8,
  "distance_trend": [ {"start": "...Z", "value": 8.4}, ... ] }
```

- **Null, not zero**: a metric with no contributing data in the period is
  `null` (a strength-only week has `distance: null`, not `0`; "no elevation
  recorded" ≠ "zero climbed"). `activity_count.total` is always a number ≥ 0.
- Unit-bearing values follow M14 exactly (converted at read time, `units` flag).
- No DB change: every input is an existing stored column (M18.1 = verified
  no-op).

### UI scope guardrails

- Cards are **display-only**; one "View all activities" link goes to the
  unfiltered feed. Filtering the list by date range is deliberately *not* in
  v1 — it belongs to the deferred reporting UI.

## Deferred / follow-ups (not M18)

- Browsable past periods + reporting UI (the API already supports it).
- Configurable week start; user-localized period boundaries ("User location +
  timezone").
- Steps (needs a data source first); streaks; per-sport PRs.
- Trend charts for other metrics (calories, HR).
