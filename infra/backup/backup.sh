#!/usr/bin/env bash
# Nightly encrypted database backup (plan §4.7 P5).
#
# Dumps the database, encrypts the dump with age (only the holder of the private key,
# kept offline, can read it), uploads it, and deletes copies older than KEEP_DAYS.
#
# Environment:
#   BACKUP_DATABASE_URL  postgresql://… (the owner role, so every workspace is included)
#   AGE_RECIPIENT        age public key, e.g. age1… (not secret)
#   BACKUP_DEST          r2:<bucket>/backups (rclone remote) or a local directory
#   KEEP_DAYS            default 30
#   RCLONE_CONFIG_R2_*   rclone settings for R2 (see docs/runbooks/deploy.md)
set -euo pipefail

: "${BACKUP_DATABASE_URL:?set BACKUP_DATABASE_URL}"
: "${AGE_RECIPIENT:?set AGE_RECIPIENT}"
: "${BACKUP_DEST:?set BACKUP_DEST}"
keep="${KEEP_DAYS:-30}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
name="companymgmt-${stamp}.dump.age"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Custom format: compressed, and restorable table by table.
pg_dump --format=custom --no-owner --no-privileges --dbname "$BACKUP_DATABASE_URL" \
  | age --encrypt --recipient "$AGE_RECIPIENT" --output "$work/$name"
size="$(wc -c < "$work/$name")"
# An encrypted empty dump is still a few hundred bytes; anything this small failed.
if [ "$size" -lt 1024 ]; then
  echo "backup too small ($size bytes); refusing to upload" >&2
  exit 1
fi
sha="$(sha256sum "$work/$name" | cut -d' ' -f1)"
echo "$sha  $name" > "$work/$name.sha256"

if [ "${BACKUP_DEST#/}" != "$BACKUP_DEST" ]; then
  mkdir -p "$BACKUP_DEST"
  cp "$work/$name" "$work/$name.sha256" "$BACKUP_DEST/"
  find "$BACKUP_DEST" -name 'companymgmt-*.dump.age*' -mtime +"$keep" -delete
else
  rclone copy "$work/" "$BACKUP_DEST/" --include "$name*"
  rclone delete "$BACKUP_DEST/" --min-age "${keep}d" --include 'companymgmt-*.dump.age*'
fi
echo "{\"backup\":\"$name\",\"bytes\":$size,\"sha256\":\"$sha\",\"kept_days\":$keep}"
