#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/formafx/storyfx
BUNDLE="${1:?versioned bundle required}"
COMMIT="${2:?verified commit required}"
[[ "$COMMIT" =~ ^[a-f0-9]{40}$ ]] || exit 20
[[ "$BUNDLE" == /tmp/storyfx-release-* ]] || exit 21
test -f "$BUNDLE/deploy/Dockerfile"
test "$(hostname)" = formafx-prod-db-02
mkdir -p "$ROOT/releases" "$ROOT/backups"
exec 9>"$ROOT/deploy.lock"
flock -n 9
RELEASE="$ROOT/releases/$COMMIT"
BACKUP="$ROOT/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 0700 "$BACKUP"
PREVIOUS=""
if [[ -L "$ROOT/current" ]]; then
  PREVIOUS="$(readlink -f "$ROOT/current")"
  [[ "$PREVIOUS" == "$ROOT/releases/"* ]] || exit 22
  printf '%s\n' "$PREVIOUS" > "$BACKUP/previous-release.txt"
fi
for file in session.key app-config.json storyfx.db storyfx.db-wal storyfx.db-shm; do
  [[ ! -L "$ROOT/state/$file" ]] || { echo 'private_symlink_refused=true'; exit 23; }
done
rollback() {
  if [[ -n "$PREVIOUS" ]]; then
    ln -sfn "$PREVIOUS" "$ROOT/current"
    STORYFX_IMAGE="formafx/storyfx:$(basename "$PREVIOUS")" docker compose -f "$PREVIOUS/deploy/compose.yaml" up -d
  else
    docker rm -f storyfx-api >/dev/null 2>&1 || true
  fi
  echo 'backend_install=failed_rolled_back'
}
trap rollback ERR
if [[ ! -d "$RELEASE" ]]; then
  mkdir "$RELEASE"
  cp -a "$BUNDLE/." "$RELEASE/"
fi
docker build --pull -t "formafx/storyfx:$COMMIT" -f "$RELEASE/deploy/Dockerfile" "$RELEASE"
if [[ -n "$PREVIOUS" ]]; then
  docker stop storyfx-api >/dev/null
elif docker inspect storyfx-api >/dev/null 2>&1; then
  echo 'unmanaged_existing_storyfx_container_refused=true'
  exit 24
fi
python3 "$RELEASE/deploy/backup_state.py" "$BACKUP"
python3 "$RELEASE/deploy/private_state.py"
STORYFX_IMAGE="formafx/storyfx:$COMMIT" docker compose -f "$RELEASE/deploy/compose.yaml" config --quiet
STORYFX_IMAGE="formafx/storyfx:$COMMIT" docker compose -f "$RELEASE/deploy/compose.yaml" up -d
for attempt in $(seq 1 30); do
  if curl -fsS --max-time 5 http://127.0.0.1:18451/health > "$BACKUP/health.json"; then break; fi
  sleep 2
done
python3 - "$BACKUP/health.json" <<'PY'
import json, sys
h = json.load(open(sys.argv[1]))
assert h['mode'] == 'diagnostic_only' and h['publishing_enabled'] is False
assert h['account_auth_enabled'] is True
PY
ln -sfn "$RELEASE" "$ROOT/current"
chmod -R go-rwx "$BACKUP"
trap - ERR
echo "backend_install=success"
echo "release=$RELEASE"
echo "rollback=$PREVIOUS"
echo "backup=$BACKUP"
