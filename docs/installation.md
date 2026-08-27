# Installation

health-tracker is a Docker-based stack: Postgres, a FastAPI backend, and a
React frontend served by nginx. Everything runs on your own hardware — there
are no cloud or third-party runtime dependencies (OpenStreetMap tiles are the
only external request the browser makes, for route maps).

## Requirements

- Docker with the Compose plugin (`docker compose`), or Docker Desktop.
- ~1 GB of RAM, a few hundred MB of disk.

No Python, Node, or Postgres is needed on the host — the containers provide
everything.

## Quick start

```bash
git clone <this-repo> health-tracker
cd health-tracker

cp .env.example .env        # then set a real JWT_SECRET (see below)
make up                     # or: docker compose up -d --build
```

`make up` builds the images, starts the database, applies any pending
migrations, and starts the API and web services. When it finishes, open
<http://localhost:9090>, create an account, and import your first activity.

To generate a strong secret:

```bash
openssl rand -hex 32
```

Put the result in `.env` as `JWT_SECRET`.

## Configuration

All configuration is passed via environment variables. Copy
`.env.example` to `.env` and adjust. Compose reads these directly:

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `healthtracker` | Postgres login user. |
| `POSTGRES_PASSWORD` | `healthtracker` | Postgres password. Change this in production. |
| `POSTGRES_DB` | `health_tracker` | Database name. |
| `JWT_SECRET` | `change-me-in-production` | Secret that signs session tokens. **Set a long random value.** |
| `JWT_TOKEN_TTL_DAYS` | `30` | How long a session token stays valid. |
| `MAX_UPLOAD_MB` | `50` | Rejected import files larger than this. (nginx's body cap is built from the same value.) |
| `MAX_TRACKPOINTS` | `100000` | Import files with more trackpoints than this are rejected. |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | Max login attempts per client IP per minute; excess gets 429. |
| `REGISTER_RATE_LIMIT_PER_MINUTE` | `5` | Max registrations per client IP per minute; excess gets 429. |
| `PUBLIC_BASE_URL` | `http://localhost:9090` | URL the browser reaches the app at; builds the provider OAuth redirect URI (default) and the post-callback redirect. Set this to your real URL if the app is not on `localhost:9090`. |
| `STRAVA_CLIENT_ID` | *(empty)* | Strava OAuth app id. Leave empty to run without Strava. |
| `STRAVA_CLIENT_SECRET` | *(empty)* | Strava OAuth app secret. |
| `STRAVA_REDIRECT_URI` | `{PUBLIC_BASE_URL}/api/v1/providers/strava/oauth/callback` | Override the OAuth redirect URI (it must exactly match one configured on the Strava app). |
| `STRAVA_SCOPE` | `activity:read_all` | Scopes requested at connect time (read-only). |
| `WEB_PORT` | `9090` | Host port the web UI is published on. |

The `DATABASE_URL`, `UPLOADS_DIR`, and the compose-built database URL are
wired automatically; you do not set them by hand in the normal Docker
workflow.

## Connecting Strava (optional)

Strava sync is opt-in and uses **your own** Strava account. The app is fully
functional without it; this is only needed to pull activities from Strava.

1. Create an OAuth app at <https://www.strava.com/settings/api> ("Create New
   App").
2. Add the **Authorization Callback Domain** or redirect URI:
   `http://localhost:9090/api/v1/providers/strava/oauth/callback`
   (use `STRAVA_REDIRECT_URI` if your app is not on that URL).
3. Copy the app's `Client ID` and `Client Secret` into `.env` as
   `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET`.
4. `make up` to restart the API. Strava now shows as *configured* under
   **Profile → Connected accounts**; connect from there.

Only the read scope (`activity:read_all`) is requested, and the app only ever
fetches the connected user's own activities — nothing is written to Strava.

## Ports

| Port | Where | Purpose |
|---|---|---|
| `9090` | host → web | The application (UI + proxied API). The only port you need. |
| `5432` | host (127.0.0.1) → db | Postgres, for local tooling (psql, local tests). |
| `8000` | host (127.0.0.1) → api | The API directly; normally unused since the web proxies `/api`. |

The Postgres and API ports are bound to `127.0.0.1` only, so they are not
reachable from the network — only `WEB_PORT` is.

## Database migrations

Schema changes are managed by [dbmate](https://github.com/amacneil/dbmate)
through the one-shot `migrate` service. Migrations run automatically on
`docker compose up`, but you can also run them by hand:

```bash
make migrate           # apply all pending migrations (up)
make migrate-down      # roll back the most recent migration
docker compose run --rm migrate status    # show applied/pending
```

Migrations live in `db/migrations/` and always include both `up` and `down`
sections.

## Updating

```bash
git pull
make up                # rebuilds changed images and restarts
```

If the update includes a new migration, it is applied automatically before the
API starts.

## Backups

All state lives in two Docker volumes:

- `pgdata` — the Postgres data (accounts, activities, metrics).
- `uploads` — the original imported files.

`make backup` captures both into a timestamped directory under `./backups/`
(set `BACKUP_DEST` for a different location):

```bash
make backup
# backups/20260825T083000Z/
#   database.dump    pg_dump custom format (-Fc): compressed, restorable
#   uploads.tar.gz   the original imported files
```

Restore with `make restore` (start the stack's `db` service if it is stopped):

```bash
docker compose stop api web      # avoid concurrent writes
make restore BACKUP=./backups/20260825T083000Z
make up
```

**Restore is destructive**: it replaces the current database contents
(`pg_restore --clean`) and the uploads volume. Take a fresh `make backup`
before restoring if you are not certain.

Notes:

- The `database.dump` in custom format restores into an empty or existing
  database with `pg_restore`; it is the recommended dump format over plain
  SQL.
- Schedule `make backup` however you like (cron, a sync to another machine);
  the two files together are a complete backup of the stack's state.

## Production notes

- Set a strong `JWT_SECRET` and `POSTGRES_PASSWORD`.
- Put the app behind a reverse proxy with TLS if you expose it beyond your LAN
  (e.g. Caddy, nginx, or Tailscale). `WEB_PORT` should then point at your
  proxy.
- Consider restricting `WEB_PORT` to your LAN instead of publishing it publicly.

## Troubleshooting

- **Port already in use** — change `WEB_PORT` in `.env` and `make up` again.
- **`/api/v1/health` shows `"status": "degraded"`** — the API is up but
  Postgres is unreachable; check `docker compose logs db`.
- **Check logs** — `docker compose logs -f api` / `... web` / `... db`.
- **Rebuild from scratch** — `docker compose build --no-cache && make up`.
