#!/usr/bin/env sh
# Deploy BankLab V2 on the VPS. Run from the repo root on the server, after
# checking out the commit to deploy (the GitHub "Deploy" workflow does this).
# Touches only the "banklab2" compose project and ~/backups/banklab2-*.
set -eu

COMPOSE="docker compose -p banklab2 -f docker-compose.prod.yml --env-file .env.prod"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"

[ -f .env.prod ] || { echo "missing .env.prod" >&2; exit 1; }
mkdir -p "$BACKUP_DIR"

echo "==> Deploying $(git rev-parse --short HEAD)"

# 1. Back up the database before migrations run (skipped on the very first deploy).
if [ -n "$($COMPOSE ps -q db 2>/dev/null)" ]; then
  stamp=$(date +%Y%m%d-%H%M%S)
  echo "==> Backup -> $BACKUP_DIR/banklab2-$stamp.dump"
  $COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' \
    > "$BACKUP_DIR/banklab2-$stamp.dump"
  find "$BACKUP_DIR" -name 'banklab2-*.dump' -mtime +"$KEEP_DAYS" -delete
fi

# 2. Build and (re)start; the backend runs migrate on start.
$COMPOSE up -d --build --remove-orphans

# 3. Wait for the backend health check.
echo "==> Waiting for backend health"
i=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' "$($COMPOSE ps -q backend)")" = "healthy" ]; do
  i=$((i + 1))
  if [ "$i" -gt 40 ]; then
    echo "backend is not healthy; recent logs:" >&2
    $COMPOSE logs --tail 80 backend >&2
    exit 1
  fi
  sleep 3
done

# 4. Remove this project's dangling images only.
docker image prune -f --filter "label=com.docker.compose.project=banklab2" >/dev/null

echo "==> Deployed $(git rev-parse --short HEAD)"
