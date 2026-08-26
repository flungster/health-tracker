#!/usr/bin/env bash
# Restore a backup produced by backup.sh.
#
#   make restore BACKUP=./backups/20260825T083000Z
#
# WARNING: destructive — replaces the current database contents and the
# uploads volume. Stop the api/web services first to avoid concurrent
# writes:  docker compose stop api web
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
UPLOADS_VOLUME="health-tracker_uploads"
ALPINE="alpine:3.20.3"

BACKUP="${1:?usage: restore.sh <backup-dir>   (make restore BACKUP=./backups/<timestamp>)}"

[ -f "$BACKUP/database.dump" ] || { echo "error: $BACKUP/database.dump not found" >&2; exit 1; }
[ -f "$BACKUP/uploads.tar.gz" ] || { echo "error: $BACKUP/uploads.tar.gz not found" >&2; exit 1; }

if [ -z "$(docker compose ps -q db)" ]; then
    echo "Database service is not running; starting it and waiting for health..."
    docker compose up -d --wait db
fi

echo "Restoring database from $BACKUP/database.dump"
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    --clean --if-exists --exit-on-error < "$BACKUP/database.dump"

echo "Restoring uploads into volume $UPLOADS_VOLUME"
BACKUP_DIR="$(cd "$BACKUP" && pwd)"
docker run --rm \
    -v "$UPLOADS_VOLUME:/dest" \
    -v "$BACKUP_DIR:/backup:ro" \
    "$ALPINE" tar -xzf /backup/uploads.tar.gz -C /dest

echo "Done. Start the rest of the stack with: make up"
