#!/usr/bin/env bash
set -euo pipefail

release_dir="${1:?usage: init-server.sh /opt/certificate-evidence/releases/<release>}"
root_dir="/opt/certificate-evidence"

case "$release_dir" in
  "$root_dir"/releases/*) ;;
  *)
    echo "release directory must be inside $root_dir/releases" >&2
    exit 1
    ;;
esac

test -d "$release_dir/deploy"

shared_dir="$root_dir/shared"
mkdir -p "$shared_dir/data/outputs"
chown -R 10001:10001 "$shared_dir/data/outputs"

find "$release_dir" -type d -exec chmod 0755 {} +
find "$release_dir" -type f -exec chmod 0644 {} +
chmod 0755 "$release_dir/deploy/init-server.sh"
chmod 0755 "$release_dir/deploy/backup-server.sh"
chmod 0755 "$release_dir/deploy/restore-server.sh"

if [[ ! -f "$shared_dir/.env" ]]; then
  cp "$release_dir/deploy/.env.example" "$shared_dir/.env"
  sed -i "s|https://verify.example.com/public/verify|http://127.0.0.1:18080/public/verify|" "$shared_dir/.env"
  sed -i "s|replace-with-a-random-password|$(openssl rand -hex 24)|" "$shared_dir/.env"
  sed -i "s|replace-with-a-different-random-password|$(openssl rand -hex 24)|" "$shared_dir/.env"
  sed -i "s|replace-with-a-random-secret|$(openssl rand -hex 32)|" "$shared_dir/.env"
fi

chmod 0600 "$shared_dir/.env"
ln -sfn "$shared_dir/.env" "$release_dir/deploy/.env"
ln -sfn "$shared_dir/data" "$release_dir/deploy/data"

cd "$release_dir/deploy"
docker compose config --quiet
echo "server initialization complete"
