# API reference

health-tracker exposes a JSON REST API under `/api/v1`. In the normal Docker
deployment the web frontend calls it same-origin through the nginx proxy, so
there is no CORS. You can also call it directly (e.g. for scripting or a
custom client) against the API on port `8000`.

## Conventions

- **Base URL** — `/api/v1` (e.g. `http://localhost:9090/api/v1`).
- **Content type** — `application/json`, except the activity import which is
  `multipart/form-data`.
- **Timestamps** — ISO 8601 in UTC (e.g. `2026-08-24T07:15:00Z`).
- **IDs** — activities and users are referenced by UUID.

### Authentication

Every endpoint except `GET /health`, `POST /auth/register`, and
`POST /auth/login` requires a bearer token:

```
Authorization: Bearer <token>
```

The token is returned by register and login. It is a JWT valid for
`JWT_TOKEN_TTL_DAYS` days (default 30).

### Error envelope

Errors always have this shape:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Activity not found.",
    "details": []
  }
}
```

| HTTP status | `code` | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid, or expired token; or bad credentials on login. |
| 404 | `NOT_FOUND` | Resource does not exist **for this user** (someone else's activity reads as 404, not 403). |
| 409 | `CONFLICT` | Conflicts with current state, e.g. registering an email that already exists. |
| 422 | `VALIDATION_ERROR` | Business-level validation failed (e.g. changing a password without the current one, an oversized upload). |
| 422 | `IMPORT_ERROR` | The uploaded file could not be parsed (wrong format, corrupt, no trackpoints, too many trackpoints). |
| 429 | `RATE_LIMITED` | Too many login/register attempts from this IP within a minute. The response carries a `Retry-After` header (seconds). |
| 500 | `INTERNAL_ERROR` | Anything unexpected. |

Note: malformed request *bodies* (wrong JSON schema) are rejected by FastAPI
itself before the app logic runs and return a 422 with a `detail` array rather
than the envelope above.

## Health

### `GET /health`

Liveness for the API and the database. Always returns 200; the `status` field
distinguishes a healthy stack from a degraded one. `version` reports the
deployed API release (see [Releasing](release.md)).

```json
{ "status": "ok", "api": "ok", "database": "ok", "version": "0.1.0" }
```

`status` is `"degraded"` and `database` is `"unreachable"` when Postgres cannot
be reached. No auth required.

## Auth

### `POST /auth/register`

Create an account. Returns 201 and a session token.

Request:

```json
{
  "first_name": "Ada",
  "last_name": "Lovelace",
  "email": "ada@example.com",
  "password": "at-least-8-chars"
}
```

- `first_name`, `last_name`: 1–100 chars, required.
- `email`: valid email, required (normalized to lowercase, must be unique).
- `password`: 8–128 chars, required.

Response `201`:

```json
{
  "user": {
    "id": "…uuid…",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "created_at": "2026-08-24T07:00:00Z"
  },
  "token": "…jwt…"
}
```

### `POST /auth/login`

Verify credentials. Returns a session token.

Request:

```json
{ "email": "ada@example.com", "password": "…" }
```

Response `200`: same shape as register (`user` + `token`). A wrong password
returns 401 `UNAUTHENTICATED`.

**Rate limit** — register and login are throttled per client IP
(`REGISTER_RATE_LIMIT_PER_MINUTE`, `LOGIN_RATE_LIMIT_PER_MINUTE`; defaults 5
and 10 per minute). Beyond the limit the response is 429 `RATE_LIMITED` with
a `Retry-After` header. The limit is in-memory and resets on an API restart.

## Users

All routes here operate on the caller's own account.

### `GET /users/me`

Return the authenticated user's account.

```json
{
  "id": "…uuid…",
  "first_name": "Ada",
  "last_name": "Lovelace",
  "email": "ada@example.com",
  "created_at": "2026-08-24T07:00:00Z"
}
```

### `PATCH /users/me`

Update account fields. Only the fields you send are changed; send at least one.
To change the password you must send both `current_password` and
`new_password`.

```json
{
  "first_name": "Ada",
  "email": "new@example.com",
  "current_password": "…",
  "new_password": "…new-one…"
}
```

Response `200`: the updated user (same shape as `GET /users/me`).

### `GET /users/me/profile`

Return the user's health settings.

```json
{ "max_heart_rate": 190, "resting_heart_rate": 60 }
```

Both fields are `null` until set.

### `PATCH /users/me/profile`

Update health settings. Only the fields you send are changed.

```json
{ "max_heart_rate": 190, "resting_heart_rate": 60 }
```

Values are integers in bpm, 30–300. Response `200`: the updated profile.

## Activities

### `POST /activities`

Import an activity file. `multipart/form-data` with:

| Part | Type | Required | Notes |
|---|---|---|---|
| `file` | file | yes | The `.gpx`, `.tcx`, or `.fit` file. At most `MAX_UPLOAD_MB` (default 50) MB and `MAX_TRACKPOINTS` (default 100,000) trackpoints. |
| `sport_type` | string | no | Override the detected sport (one of `GET /sports`). |
| `name` | string | no | Override the activity name. |

Limits: a file larger than `MAX_UPLOAD_MB` is rejected with 422
`VALIDATION_ERROR`; a file with more than `MAX_TRACKPOINTS` trackpoints is
rejected with 422 `IMPORT_ERROR`.

Example with `curl`:

```bash
curl -X POST http://localhost:9090/api/v1/activities \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@run.gpx" \
  -F "sport_type=running" \
  -F "name=Morning run"
```

Response `201`: the full activity detail (see `GET /activities/{id}`).
Errors: 422 `IMPORT_ERROR` if the file cannot be parsed, 413/422 if it exceeds
`MAX_UPLOAD_MB`.

### `GET /activities`

The caller's activities, newest first, paginated.

Query parameters:

| Param | Default | Bounds |
|---|---|---|
| `limit` | `25` | 1–100 |
| `offset` | `0` | ≥ 0 |

Response `200`:

```json
{
  "items": [
    {
      "id": "…uuid…",
      "sport_type": "running",
      "name": "Morning run",
      "started_at": "2026-08-24T07:15:00Z",
      "duration_seconds": 2850,
      "moving_seconds": 2800,
      "distance_m": 5054.3,
      "calories_kcal": 410.5,
      "elevation_gain_m": 88.0,
      "heart_rate_avg_bpm": 152
    }
  ],
  "total": 42,
  "limit": 25,
  "offset": 0
}
```

### `GET /activities/{id}`

Full detail for one of the caller's activities.

```json
{
  "id": "…uuid…",
  "sport_type": "running",
  "name": "Morning run",
  "description": null,
  "started_at": "2026-08-24T07:15:00Z",
  "ended_at": "2026-08-24T08:02:30Z",
  "duration_seconds": 2850,
  "moving_seconds": 2800,
  "distance_m": 5054.3,
  "calories_kcal": 410.5,
  "elevation_gain_m": 88.0,
  "heart_rate_min_bpm": 96,
  "heart_rate_avg_bpm": 152,
  "heart_rate_max_bpm": 178,
  "cadence_avg_rpm": 171,
  "source_format": "gpx",
  "original_filename": "run.gpx",
  "created_at": "2026-08-24T08:05:00Z",
  "splits": [
    {
      "split_type": "km",
      "split_index": 1,
      "duration_seconds": 293,
      "pace_seconds": 293,
      "heart_rate_avg_bpm": 149,
      "cadence_avg_rpm": 170
    }
  ],
  "heart_rate_zones": {
    "zone_1_seconds": 0,
    "zone_2_seconds": 1200,
    "zone_3_seconds": 900,
    "zone_4_seconds": 600,
    "zone_5_seconds": 150
  },
  "running": {
    "avg_pace_s_per_km": 292.8,
    "min_pace_s_per_km": 280.0,
    "max_pace_s_per_km": 300.0
  },
  "cycling": null,
  "rowing": null,
  "strength": null
}
```

Notes:
- `splits` contains both `km` and `mi` rows, precomputed at import.
- `heart_rate_zones` is `null` when the activity has no heart-rate data.
- Exactly one of `running` / `cycling` / `rowing` / `strength` is populated,
  matching `sport_type`; the rest are `null`. (Other sports such as yoga,
  hiking, walking, swimming, and other carry no dedicated metrics object.)

### `GET /activities/{id}/trackpoints`

All recorded samples, in order.

```json
{
  "items": [
    {
      "seq": 0,
      "recorded_at": "2026-08-24T07:15:00Z",
      "lat": 47.36,
      "lon": 8.54,
      "altitude_m": 520.0,
      "heart_rate_bpm": 120,
      "cadence_rpm": 170,
      "speed_mps": 3.4,
      "power_w": null
    }
  ]
}
```

Any field may be `null` when the source did not record it (e.g. `lat`/`lon` for
non-GPS samples, `power_w` for non-cycling).

### `GET /activities/{id}/splits`

The precomputed splits only.

```json
{
  "items": [
    {
      "split_type": "km",
      "split_index": 1,
      "duration_seconds": 293,
      "pace_seconds": 293,
      "heart_rate_avg_bpm": 149,
      "cadence_avg_rpm": 170
    }
  ]
}
```

### `PATCH /activities/{id}`

Update name, description, and/or sport. Send at least one field.

```json
{ "name": "Tempo run", "sport_type": "running" }
```

- `name`: 1–200 chars.
- `description`: up to 2000 chars (send `""` or a string to set; send `null` to leave unchanged).
- `sport_type`: one of `GET /sports`.

Response `200`: the updated activity detail (full shape). Changing `sport_type`
does **not** recompute the derived metrics — it only relabels the activity.

### `DELETE /activities/{id}`

Soft-delete one of the caller's activities. Response `204` (no body). The
activity then disappears from `GET /activities` and its detail reads as 404.

## Sports

### `GET /sports`

The canonical list of sport types, from the `activity_types` reference table,
in `value` order. Each entry carries the public `value` (used in import
overrides and activity responses) and a human-readable `description` for
display. No auth required.

```json
{
  "sports": [
    { "value": "cycling",  "description": "Cycling" },
    { "value": "hiking",   "description": "Hiking" },
    { "value": "other",    "description": "Other" },
    { "value": "rowing",   "description": "Rowing" },
    { "value": "running",  "description": "Running" },
    { "value": "strength", "description": "Strength" },
    { "value": "swimming", "description": "Swimming" },
    { "value": "walking",  "description": "Walking" },
    { "value": "yoga",     "description": "Yoga" }
  ]
}
```
