#!/usr/bin/env bash
# Creates the local roles and databases. Safe to run more than once.
#
#   cm_owner  owns the schema and runs migrations
#   cm_app    what the API connects as: no table ownership, no BYPASSRLS
#
# Uses ADMIN_DATABASE_URL (a superuser connection) if set, otherwise `sudo -u postgres`.
set -euo pipefail

owner_pw="${CM_OWNER_PASSWORD:-cm_owner}"
app_pw="${CM_APP_PASSWORD:-cm_app}"

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
END \$\$;
GRANT cm_app TO cm_owner;
SQL

for db in companymgmt companymgmt_test; do
  exists=$(psql_admin -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'")
  if [ "$exists" != "1" ]; then
    psql_admin -q -c "CREATE DATABASE $db OWNER cm_owner"
  fi
  psql_admin -q -d "$db" -c "CREATE EXTENSION IF NOT EXISTS citext; REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO cm_app; ALTER SCHEMA public OWNER TO cm_owner;"
done

echo "Local databases ready: companymgmt, companymgmt_test"
