#!/usr/bin/env bash
# Back up the database and the original uploaded files.
#
#   make backup                  # -> backups/<utc-timestamp>/{database.dump,uploads.tar.gz}
#   BACKUP_DEST=/path make backup  # write to a specific directory
#
# The dump is in pg_dump's custom format (-Fc): compressed, and restorable
# into a (possibly empty) database with pg_restore.
set -euo pipefail
cd "$(dirname "$0")/.."

# Pick up POSTGRES_* (and friends) from .env when present.
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

POSTGRES_USER="${POSTGRES_USER:-healthtracker}"
POSTGRES_DB="${POSTGRES_DB:-health_tracker}"
# The compose project name is fixed in docker-compose.yml, so the volume
# name is deterministic.
UPLOADS_VOLUME="health-tracker_uploads"
# Pinned helper image (only needs tar).
ALPINE="alpine:3.20.3"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_DEST:-backups/$STAMP}"

if ! docker volume inspect "$UPLOADS_VOLUME" > /dev/null 2>&1; then
    echo "error: docker volume $UPLOADS_VOLUME not found (has the stack been built?)" >&2
    exit 1
fi

mkdir -p "$DEST"
echo "Backing up to $DEST"

echo "  database -> $DEST/database.dump"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" \
    > "$DEST/database.dump"

echo "  uploads  -> $DEST/uploads.tar.gz"
docker run --rm -v "$UPLOADS_VOLUME:/src:ro" "$ALPINE" tar -czf - -C /src . \
    > "$DEST/uploads.tar.gz"

echo "Done. Keep the backup directory somewhere outside the repo (it is not git-ignored content you want to commit)."
