# Usage

A walkthrough of health-tracker from the point of view of someone using the web
UI.

## Getting started

1. Open the app (default <http://localhost:9090>).
2. Click **Create an account**, enter your name, email, and a password
   (8+ characters). You are signed in immediately.
3. Your home page is the **Dashboard** — a snapshot of today (or this week).
   The full chronological feed is under **Activities** in the top nav.

## Dashboard

The home page (the `health-tracker` brand in the header, or `/`) answers
"what did I do this day / week / month / year?" at a glance:

- A **Day / Week / Month / Year** switcher picks the period (defaults to
  *Week*). The choice is remembered in your browser and appears in the URL as
  `?period=week`, so a link shares that view. Week runs Monday–Sunday, and all
  boundaries follow your **local** date (the same rule as the feed's *Today* /
  *Yesterday*). You can only view the current period — browsing past periods is
  not a v1 feature.
- Seven cards, for the period: **Activities** (with per-sport chips),
  **Moving time**, **Distance**, **Elevation gain**, **Calories** (kcal, never
  converted), **Avg heart rate** (the mean of your activities' average HRs) and
  **Weight lifted** (total strength volume). A card shows **—** when no
  activity in the period has that metric ("no distance recorded" is not "zero
  travelled"). All unit-bearing values follow your [unit system](#units-of-measurement).
- **Distance over time** chart: one bar per day (Week/Month) or per month
  (Year). It is hidden on the Day view and stays empty when nothing in the
  period has a distance.

The cards are display-only — **View all activities** takes you to the
unfiltered feed.

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

The **Activities** page (`/activities`) lists your activities grouped by day
(local date of the activity's start time), newest first — *Today*,
*Yesterday*, then full dates. Each card shows the sport, name, date/time,
distance, duration, average heart rate, and calories. Activities fetched from a
connected account also show the provider's name (e.g. **Strava**) — file
imports carry no badge, so a bare card is one you uploaded yourself. **Load
more** pulls in older activities.

## Activity detail

Clicking an activity opens its detail page:

- **Header** — sport badge (plus the provider's name when it came from a
  connected account), name (click to rename inline), start date/time, and an
  optional description. A **Delete** button removes the activity (soft delete;
  confirm in the dialog).
- **Stat grid** — distance, time, moving time, elevation gain, calories,
  average pace, average/max heart rate, average cadence. Missing values are
  hidden.
- **Photos** — your photos for this activity (optional). Drag one or more
  images onto the **Add photos** tile, or click it to browse — JPEG, PNG and
  WebP up to the upload limit. Click a photo to view it full-size (close with
  Escape or by clicking away); hover for the × button to remove it (confirmed in
  a dialog). Photos are stored on your server — they never leave it.
- **Route map** — the GPS route on an OpenStreetMap map, shown only when the
  activity has GPS points.
- **Splits** — one table in your display unit system (per-kilometre or
  per-mile), each row showing split time, pace, and — only when recorded —
  average heart rate and cadence. (An activity shorter than a tenth of one unit
  has no splits for that system.)
- **Heart rate** — a line chart of heart rate across the activity.
- **Time in heart-rate zones** — a bar chart of the seconds spent in each of
  the five zones (see below; needs a zone reference set on your profile).
- **Sport metrics** — a panel for the activity's sport (running pace, cycling
  power, rowing distance / stroke rate / 500 m split, strength volume).

## Units of measurement

Everything distance-related is shown in your **display unit system** — metric or
imperial, chosen on the **Profile** page. It is per-user and stored on your
profile: distances (m/km vs miles), elevation gain, running pace (/km vs /mi),
and strength volume (kg vs lb). Calories, heart rate, cadence, power, and time
are never converted; rowing's 500 m split stays in metres either way.

Your stored data is never changed — values are converted at read time, so
switching back restores the exact figures you imported. The choice applies to
everything you see immediately, and is remembered on this device in the meantime
so it pre-paints before your profile loads.

## Heart-rate zones

Zones are personal: health-tracker computes them against a **zone reference**
from your profile, resolved with fixed precedence —

1. **Custom zones**, if you set all four boundaries on the **Profile** page;
2. otherwise your **max heart rate**, set on the **Profile** page;
3. otherwise an **age-derived** max heart rate (`220 - age`, if you set a date
   of birth on the **Profile** page).

The Profile card shows which reference is currently in effect. They are
computed when you open an activity (from its recorded heart-rate samples), so
if you later change your profile, the zones update on **every** activity
immediately — no re-importing anything.

If none of the three is set, the zone chart is not shown (an activity's own max
HR is not a fair reference — it would make every activity look like mostly zone
5); the page links you to your profile to set a max heart rate.

For custom zones, each boundary is an explicit bpm cutoff (zone 1 is at or
below the first top, zone *n* is above the *(n−1)*th top and at or below the
*n*th, zone 5 is above the fourth). The four tops must be strictly ascending —
enter all of them or none. For a max-heart-rate or age-derived reference,
boundaries are percent of that max HR:

| Zone | Range | Meaning |
|---|---|---|
| 1 | < 56% | warmup |
| 2 | 56–63% | easy |
| 3 | 64–71% | tempo |
| 4 | 72–80% | threshold |
| 5 | > 80% | VO2 max |

## Profile

The **Profile** page has five parts:

- **Account** — your name, email, and join date.
- **Units of measurement** — choose metric or imperial for all displayed
  distances, elevations and paces (see *Units of measurement*). The change is
  saved as soon as you pick it.
- **Connected accounts** — connect or disconnect a third-party service (e.g.
  Strava) and sync your activities from it.
- **Heart-rate zones** — set your max and resting heart rate (bpm), an optional
  date of birth, and up to four custom zone boundaries. The card shows which
  reference your activities' zones are currently computed from (custom > max HR
  > age). With none set, no zone chart is shown.
- **Change password** — verify your current password and set a new one.

## Connected accounts

A **connected account** links one of *your own* third-party profiles (e.g.
Strava) to your local account. The app reads only your own activities and
never writes to the service. Everything imported still lands in your local
data, where it is yours to keep.

- **Connect** — on the Profile page, click **Connect** for a service. You are
  sent to the service's authorization page; approve it and you are returned
  here with a confirmation. Only services configured on this server are
  connectable — others show as "Not configured on this server" with a link to
  the [Server settings](#server-settings) page.
- **Sync** — click **Sync** on a connected service to pull your activities
  from it. The first sync imports your whole history; later syncs only add
  what is new (the row shows when it was last synced). A very large history
  may take more than one sync — just run it again.
- **Import from** — each connection has an import-from floor, set from the
  connected row: **All time** (the default — import everything), **30 days**,
  **90 days**, **1 year**, or a custom date. Syncs import only activities
  started on or after the floor, which also makes re-syncs cheap for a huge
  history you do not care about. The floor is your preference: it survives
  disconnecting and reconnecting.
- **Rescan from…** — for a one-off run, pick any date and the next sync
  re-walks the history from there (already-imported activities are skipped).
  It does not change the saved import-from floor.
- **Disconnect** — click **Disconnect** on a connected service. This revokes
  the connection at the service and stops it from being used. Activities you
  already imported remain in your data.

## Server settings

The **Server settings** page (top nav) is where this server's connections to
third-party services are configured — the *app* your accounts connect through,
not your personal accounts. Any account on the server can change these
settings. Each provider card carries a collapsible **How do I get these?**
block with the setup steps, including this server's exact callback URL.

For each provider (Strava for now):

1. Create an OAuth app in the provider's developer settings (for Strava:
   <https://www.strava.com/settings/api> → "Create New App"), with the
   redirect URI `{PUBLIC_BASE_URL}/api/v1/providers/strava/oauth/callback`
   (default `http://localhost:9090/api/v1/providers/strava/oauth/callback`).
2. Enter the app's **Client ID** and **Client secret** on the Server settings
   page and click **Save**. The secret is stored encrypted and is never shown
   again — on a later save, leave the field blank to keep the current secret.
   An optional **Display name** labels the provider in the UI.
3. The provider is immediately usable (no restart): **Connect** appears on the
   Profile page.

**Remove** deletes the server's client for a provider. People's existing
connections are not deleted — they are paused ("Sync paused" on the Profile
page) until the app is added again; re-saving it resumes syncing with the
tokens they already granted.

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
