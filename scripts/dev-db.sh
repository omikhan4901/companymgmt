#!/usr/bin/env bash
# Creates the local roles and databases. Safe to run more than once.
#
#   cm_owner  owns the schema and runs migrations
#   cm_app    what the API connects as: no table ownership, no BYPASSRLS
#   cm_backup reads everything for the nightly backup (BYPASSRLS, SELECT only)
#
# Uses ADMIN_DATABASE_URL (a superuser connection) if set, otherwise `sudo -u postgres`.
set -euo pipefail

owner_pw="${CM_OWNER_PASSWORD:-cm_owner}"
app_pw="${CM_APP_PASSWORD:-cm_app}"
backup_pw="${CM_BACKUP_PASSWORD:-cm_backup}"

# psql_admin [-d DB] …: runs as a superuser, optionally in a given database.
psql_admin() {
  local db="postgres"
  if [ "${1:-}" = "-d" ]; then db="$2"; shift 2; fi
  if [ -n "${ADMIN_DATABASE_URL:-}" ]; then
    psql "${ADMIN_DATABASE_URL%/*}/$db" -v ON_ERROR_STOP=1 "$@"
  elif [ "$(id -u)" = "0" ]; then
    su postgres -c "psql -d $db -v ON_ERROR_STOP=1 $(printf '%q ' "$@")"
  else
    sudo -u postgres psql -d "$db" -v ON_ERROR_STOP=1 "$@"
  fi
}

psql_admin -q <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cm_owner') THEN
    CREATE ROLE cm_owner LOGIN CREATEDB PASSWORD '${owner_pw}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cm_app') THEN
    CREATE ROLE cm_app LOGIN NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '${app_pw}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cm_backup') THEN
    CREATE ROLE cm_backup LOGIN BYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '${backup_pw}';
  END IF;
END \$\$;
GRANT cm_app TO cm_owner;
SQL

for db in companymgmt companymgmt_test; do
  exists=$(psql_admin -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'")
  if [ "$exists" != "1" ]; then
    psql_admin -q -c "CREATE DATABASE $db OWNER cm_owner"
  fi
  psql_admin -d "$db" -q -c "CREATE EXTENSION IF NOT EXISTS citext; REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO cm_app; ALTER SCHEMA public OWNER TO cm_owner;"
  # Backups read every table, now and in the future, and can change nothing.
  psql_admin -d "$db" -q -c "GRANT USAGE ON SCHEMA public TO cm_backup; GRANT SELECT ON ALL TABLES IN SCHEMA public TO cm_backup; GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO cm_backup; ALTER DEFAULT PRIVILEGES FOR ROLE cm_owner IN SCHEMA public GRANT SELECT ON TABLES TO cm_backup; ALTER DEFAULT PRIVILEGES FOR ROLE cm_owner IN SCHEMA public GRANT SELECT ON SEQUENCES TO cm_backup;"
done

echo "Local databases ready: companymgmt, companymgmt_test"
