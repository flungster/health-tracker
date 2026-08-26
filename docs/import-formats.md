# Import formats

health-tracker imports activity files in three formats: **GPX**, **TCX**, and
**FIT**. Each is parsed into the same format-neutral `ParsedActivity` structure
(see `api/app/imports/parsed.py`), so the rest of the app never depends on a
specific format. This page documents what each format contributes and the
rules applied across all of them.

## How a file is read

1. **Detect** — the `FormatDetector` inspects the file. FIT files are
   recognized first by their magic header (a size byte of `0x0C` or `0x0E` at
   offset 0 and the ASCII `".FIT"` at offset 8); otherwise the file extension
   chooses between GPX and TCX. An unknown format is rejected with a 422
   `IMPORT_ERROR`.
2. **Parse** — the matching parser turns the raw bytes into a `ParsedActivity`.
   Parsers are pure and null-safe: any missing field stays `null` rather than
   raising, and problems are recorded in `ParsedActivity.warnings`.
3. **Validate** — the import service requires at least a start time and
   trackpoint data; otherwise it rejects the file with `IMPORT_ERROR`.

## What each format provides

### GPX (via `gpxpy`)

The most portable GPS format. Parsed from the `<trk>` elements:

- Trackpoints: time, latitude, longitude, elevation.
- Per-point heart rate, cadence, power, and speed read from `<extensions>` in a
  vendor-namespace-agnostic way (Garmin, Suunto, and similar are all handled
  by looking up the local element names regardless of namespace).
- Name from `<metadata><name>` (falling back to `<trk><name>`).
- Sport from `<trk><type>`.

### TCX (in-repo parser over `xml.etree.ElementTree`)

The Garmin Training Center XML format. There is no maintained Python TCX
library, so health-tracker ships a small in-repo parser:

- Trackpoints and their `<Extensions>` (heart rate, cadence, power).
- Sport, name, start/end times, and distance from `<Lap>` / `<Activity>` /
  `<Summary>` elements, using namespace-free local-name lookups.
- Per-lap distance and moving-time accumulation.

### FIT (via `fitdecode`)

The binary Garmin format. Parsed with the strict fitdecode iterator API:

- Record messages (position, time, heart rate, cadence, speed, power).
- Session messages for the summary: sport, distance, calories, ascent, and
  heart-rate/power statistics.
- Positions are stored as raw integers scaled by 1e-7 degrees (per the FIT
  spec) and converted to decimal degrees.
- CRC is verified strictly; a corrupt or truncated file is rejected.

## Cross-format rules

- **`0` means "no data".** Devices report `0` for cadence, power, and heart
  rate when a sensor is absent or momentarily invalid. Because the database
  constrains these columns to `> 0`, the parsers normalize `0` → `null` so a
  "no reading" is stored as an absent value, not a bogus zero.
- **Sport resolution.** Vendor files spell the same sport many ways.
  `resolve_sport()` folds known labels into the canonical set:

  | Canonical | Recognized labels (examples) |
  |---|---|
  | running | "run", "run mode", "trail run", "marathon", "treadmill" |
  | cycling | "bike", "indoor bike", "virtual ride", "spinning", "mountain bike" |
  | rowing | "indoor rower", "indoor rowing", "rowing machine" |
  | strength | "weight training", "weights", "strength training" |
  | hiking | "hike", "trail" |
  | walking | "walk" |
  | swimming | "open water swim", "pool swim" |
  | yoga | "yoga" |

  A label the app doesn't recognize maps to `other`. When a file carries no
  sport information at all, the import service applies the default
  (**running**), unless you override the sport on the upload page. The upload
  page's sport override wins over everything.
- **Name resolution.** The display name is taken from the file when present,
  otherwise from the file name (without extension); the upload page's title
  override wins.
- **GPS is optional.** Activities without position data (e.g. treadmill,
  indoor rower, strength) still import; they simply have no route map and a
  `null` distance unless the device recorded one.
- **Heart-rate zones** are computed at import from the trackpoint heart rates
  and the user's profile max HR (or the activity's own max HR when unset). See
  [usage.md](usage.md#heart-rate-zones).

## Errors

A file that is not a valid GPX/TCX/FIT activity — wrong format, corrupt data,
bad CRC, no trackpoints, or no timestamps — is rejected with a 422 and the
`IMPORT_ERROR` code. No partial activity is created.
