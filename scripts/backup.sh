#!/bin/sh
set -eu

backup_root="${BACKUP_ROOT:-./backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="$backup_root/$timestamp"
mkdir -p "$destination"

pg_dump "${PG_BACKUP_URL:?PG_BACKUP_URL is required (standard postgresql:// URL)}" --format=custom --file="$destination/database.dump"
report_file_root="${REPORT_FILE_ROOT:-./data/technical-reports}"
if [ -d "$report_file_root" ]; then
  tar -czf "$destination/technical-reports.tar.gz" -C "$report_file_root" .
fi
find "$backup_root" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf -- {} +
echo "Backup created at $destination"
