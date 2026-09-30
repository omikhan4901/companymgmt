# Restoring data

## What exists today

- **Neon point-in-time restore**: every change is kept for the plan's history window
  (Free: 6 hours; Launch: up to 7 days). This is the main recovery tool in Milestone 1.
- **Planned (not built yet)**: a nightly encrypted `pg_dump` to Cloudflare R2 kept for 30
  days, for longer history and single-workspace restores (plan §4.7 P5). Tracked in
  `docs/PROGRESS.md`.

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

## One workspace only

Until the nightly dumps exist, restore into a separate Neon branch as above, then copy
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
