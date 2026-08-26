# Usage

A walkthrough of health-tracker from the point of view of someone using the web
UI.

## Getting started

1. Open the app (default <http://localhost:9090>).
2. Click **Create an account**, enter your name, email, and a password
   (8+ characters). You are signed in immediately.
3. Your home page is the **Activities** feed — empty until you import something.

## Importing an activity

1. Click **Upload activity** (top nav or the **+ Upload activity** button).
2. Drag a file onto the drop zone, or click it to browse. Supported formats:
   `.gpx`, `.tcx`, `.fit`.
3. Optionally override the **Sport** (defaults to *Detect from file*) and add a
   **Title** (defaults to the name in the file, then the file name).
4. Click **Import activity**. On success you land on the new activity's detail
   page.

The original file is stored on your machine in the uploads volume; health-
tracker never sends it anywhere else.

### What happens on import

health-tracker reads the file, extracts the GPS/physiology samples, and derives
a lot for you in one step:

- total distance, duration, moving time, elevation gain, calories
- min / avg / max heart rate and average cadence
- per-kilometre and per-mile **splits** (with per-split heart rate and cadence)
- **heart-rate zones** (time in each of five zones)
- sport-specific metrics (pace for running, power for cycling, stroke rate and
  500 m split for rowing, volume for strength)

### Supported file details

See [import-formats.md](import-formats.md) for exactly which fields each format
contributes and how vendor labels are handled.

## The activity feed

The feed lists your activities grouped by day (local date of the activity's
start time), newest first — *Today*, *Yesterday*, then full dates. Each card
shows the sport, name, date/time, distance, duration, average heart rate, and
calories. **Load more** pulls in older activities.

## Activity detail

Clicking an activity opens its detail page:

- **Header** — sport badge, name (click to rename inline), start date/time, and
  an optional description. A **Delete** button removes the activity (soft
  delete; confirm in the dialog).
- **Stat grid** — distance, time, moving time, elevation gain, calories,
  average pace, average/max heart rate, average cadence. Missing values are
  hidden.
- **Route map** — the GPS route on an OpenStreetMap map, shown only when the
  activity has GPS points.
- **Splits** — a per-kilometre table and (where relevant) a per-mile table,
  each row showing split time, pace, and — only when recorded — average heart
  rate and cadence.
- **Heart rate** — a line chart of heart rate across the activity.
- **Time in heart-rate zones** — a bar chart of the seconds spent in each of
  the five zones.
- **Sport metrics** — a panel for the activity's sport (running pace, cycling
  power, rowing stroke rate / 500 m split, strength volume).

## Heart-rate zones

Zones are computed from a maximum heart rate. health-tracker uses your
**profile max heart rate** when you have set one; otherwise it falls back to
the activity's own max heart rate. Boundaries (percent of max HR):

| Zone | Range | Meaning |
|---|---|---|
| 1 | < 56% | warmup |
| 2 | 56–63% | easy |
| 3 | 64–71% | tempo |
| 4 | 72–80% | threshold |
| 5 | > 80% | VO2 max |

Set your max (and optionally resting) heart rate on the **Profile** page to get
consistent zones across all activities.

## Profile

The **Profile** page has three parts:

- **Account** — your name, email, and join date.
- **Heart-rate zones** — set your max and resting heart rate (bpm). This drives
  the zone chart on every activity.
- **Change password** — verify your current password and set a new one.

## Managing activities

- **Rename** — on the detail page, click the activity title and type a new name
  (Enter saves, Esc cancels).
- **Delete** — click **Delete** on the detail page and confirm. The activity is
  removed from your feed.

## Sports

health-tracker recognizes these sport types: running, cycling, rowing,
strength, yoga, hiking, walking, swimming, and other. The sport is taken from
the file when it records one (vendor labels like "Run Mode" or "Indoor Rower"
are folded into these), overridden by your choice on the upload page, and
defaults to **running** when the file carries no sport at all.
