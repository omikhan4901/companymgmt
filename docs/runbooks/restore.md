# Restoring data

## What exists today

- **Neon point-in-time restore**: every change is kept for the plan's history window
  (Free: 6 hours; Launch: up to 7 days). This is the main recovery tool in Milestone 1.
- **Nightly encrypted dumps**: the `companymgmt-backup` job runs `pg_dump` as `cm_backup`,
  encrypts it with `age` to the public key in `BACKUP_AGE_RECIPIENT`, and uploads it to
  the R2 bucket under `db/`, keeping 30 days (plan §4.7 P5). Each dump has a `.sha256`
  next to it.

## Full restore (the whole database)

1. Neon console → the project → **Branches → Create branch** from `main` **at a point in
   time** just before the problem.
2. Check the branch: **SQL Editor** on the new branch, e.g.
   `SELECT count(*) FROM tenants; SELECT max(occurred_at) FROM audit_events;`
3. Verify the audit chain on the branch (tampering or corruption shows here): point a local
   API at the branch (`DATABASE_URL`) and call `GET /v1/audit/verify` per workspace, or run
   the same query the API uses.
4. Neon → **Restore** the `main` branch from that point (or promote the checked branch).
   Neon keeps a backup of the pre-restore state for undo.
5. Note the incident, what was lost (writes after the restore point), and tell affected
   workspace owners.

## From a nightly dump

1. Download the dump and its checksum from R2 (`db/companymgmt-<time>.dump.age`), check
   it with `sha256sum -c companymgmt-<time>.dump.age.sha256`.
2. Decrypt on your own computer with the offline key:
   `age --decrypt -i backup-key.txt companymgmt-<time>.dump.age > companymgmt.dump`
3. Restore into a new, empty database (a new Neon branch or a local Postgres) as the owner:
   `pg_restore --no-owner --dbname "$NEW_DATABASE_URL" companymgmt.dump`
4. Check it: `SELECT version_num FROM alembic_version;` matches the code, then the steps
   in "Full restore" from step 2. Delete the decrypted file when done.

This was drilled locally on 1 Oct 2026: a dump of the development database decrypted and
restored with every table, its row-level security and the migration version intact.

## One workspace only

Restore into a separate Neon branch (or from a nightly dump, as above), then copy
that workspace's rows back with `INSERT … SELECT` for each table, filtered by
`tenant_id`, in foreign-key order (roles → memberships → departments → employees →
branches → attendance). Run it as `cm_owner` with `app.tenant_id` set to the workspace.
Test on a scratch branch first.

## Drill (every quarter)

Create a point-in-time branch from 24 hours ago, check row counts against production,
verify one workspace's audit chain, delete the branch. Write the date and result in this
file.

| Date | Who | Result |
|---|---|---|
| | | |
