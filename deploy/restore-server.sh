#!/usr/bin/env bash
set -euo pipefail

backup_dir="${1:?usage: CONFIRM_RESTORE=certificate-evidence restore-server.sh /opt/certificate-evidence/backups/<timestamp>}"
root_dir="/opt/certificate-evidence"
release_dir="$(readlink -f "$root_dir/current")"
resolved_backup="$(readlink -f "$backup_dir")"

if [[ "${CONFIRM_RESTORE:-}" != "certificate-evidence" ]]; then
  echo "set CONFIRM_RESTORE=certificate-evidence to confirm this destructive restore" >&2
  exit 1
fi

case "$resolved_backup" in
  "$root_dir"/backups/*) ;;
  *)
    echo "backup directory must resolve inside $root_dir/backups" >&2
    exit 1
    ;;
esac

test -f "$resolved_backup/database.sql"
test -f "$resolved_backup/outputs.tar.gz"
test -f "$resolved_backup/SHA256SUMS"

cd "$resolved_backup"
sha256sum --check SHA256SUMS

"$release_dir/deploy/backup-server.sh" "$release_dir" >/dev/null

cd "$release_dir/deploy"
docker compose stop web backend
docker compose exec -T db sh -c 'exec mysql -ucertificate -p"$MYSQL_PASSWORD" certificate_evidence' < "$resolved_backup/database.sql"
tar -xzf "$resolved_backup/outputs.tar.gz" -C "$root_dir/shared/data"
chown -R 10001:10001 "$root_dir/shared/data/outputs"
docker compose up -d
curl --fail --silent --show-error --retry 20 --retry-delay 3 --retry-connrefused --retry-all-errors http://127.0.0.1:18080/api/health/db >/dev/null

echo "restore complete"
