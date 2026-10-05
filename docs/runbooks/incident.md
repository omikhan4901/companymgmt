# Incident response

For security incidents (a leak, an account takeover, a suspicious change) and outages.
Keep a timeline in a private document as you go: what you saw, when, what you did.

## 1. Triage (first 15 minutes)

- **Is data exposed or being changed right now?** Treat it as a security incident.
- **Is the service down or wrong for everyone?** An outage: go to §4.
- Write down: first sign, time (UTC), who noticed, what's affected.

## 2. Contain

| Situation | Do this |
|---|---|
| A person's account is taken over | Members → the person → remove, or have them reset their password (all sessions end). Their sessions: Account → Sessions → sign out everywhere. |
| An API key leaked | Settings → Developers → API keys → Revoke (immediate). Check its usage and the audit log for what it did. |
| A webhook secret leaked | Settings → Developers → Webhooks → New signing secret. |
| A till device was stolen | Sales → Tills → Remove till (its sessions end at once). |
| Everyone must be signed out | Rotate `JWT_PRIVATE_KEY` (access tokens stop at once) and run `UPDATE auth_sessions SET revoked_at = now(), revoke_reason = 'incident' WHERE revoked_at IS NULL;` |
| A server secret leaked (database password, encryption key, internal token) | Rotate it in Secret Manager and redeploy (`runbooks/deploy.md`). For the field encryption key, add a new key id and make it active; old data stays readable with the old id. |
| A bad deploy | Roll back to the previous Cloud Run revision (`gcloud run services update-traffic companymgmt-api --to-revisions=<previous>=100`). |
| Data was changed or deleted | Restore from point in time (`runbooks/restore.md`) to a branch, compare, and copy back what's needed. Check the audit chain (`GET /v1/audit/verify`). |

## 3. Investigate

- Audit log per workspace (Settings → Audit log; export as CSV/JSONL) shows who changed
  what, from which address, with request ids.
- `auth_events` (global) shows sign-ins, failures, new devices, refresh-token reuse.
- Cloud Run logs are JSON with `request_id`; search by it.
- Webhook delivery logs and API key usage show what integrations did.

## 4. Outages

1. Check `/healthz` and `/readyz`, Cloud Run status and Neon status.
2. Look at the latest deploy; roll back if it's recent (above).
3. Database full or slow: Neon console (compute size, storage, long queries).
4. Post a short note on the status page (see below) and update it every 30 minutes.

## 5. Tell people

- **Personal data breach:** tell affected workspace owners without undue delay, with what
  happened, what data, what you did and what they should do. Where the GDPR or a local
  law applies, the controller (the workspace) may have 72 hours to notify a regulator, so
  tell them fast. The legal review sets the exact duties per country.
- Keep the message plain and factual. Don't guess at causes before you know.

## 6. Afterwards

Within a week: a short write-up (timeline, cause, what stopped it, what changes so it
can't happen again), with the fixes as tasks. Add a test for the cause.

## Status page

Use a free hosted status page with uptime checks (for example Better Stack or UptimeRobot,
both have free tiers) pointed at `https://companymgmt.app/` and the API's `/healthz`, at
`status.companymgmt.app`. Link it from the site footer once it exists.
