#!/usr/bin/env bash
set -euo pipefail

release_dir="${1:-/opt/certificate-evidence/current}"
root_dir="/opt/certificate-evidence"
resolved_release="$(readlink -f "$release_dir")"

case "$resolved_release" in
  "$root_dir"/releases/*) ;;
  *)
    echo "release directory must resolve inside $root_dir/releases" >&2
    exit 1
    ;;
esac

timestamp="$(date -u +%Y%m%d-%H%M%S)"
backup_dir="$root_dir/backups/$timestamp"
umask 077
mkdir -p "$backup_dir"

cd "$resolved_release/deploy"
docker compose exec -T db sh -c 'exec mysqldump -ucertificate -p"$MYSQL_PASSWORD" --single-transaction --no-tablespaces --routines --triggers certificate_evidence' > "$backup_dir/database.sql"
tar -czf "$backup_dir/outputs.tar.gz" -C "$root_dir/shared/data" outputs
sha256sum "$backup_dir/database.sql" "$backup_dir/outputs.tar.gz" > "$backup_dir/SHA256SUMS"

echo "$backup_dir"
