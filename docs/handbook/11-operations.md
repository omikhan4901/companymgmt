# 11. Operating it

## 11.1 Your weekly routine

| When | What | How |
|---|---|---|
| Every change | run the gate, then push | `scripts/check.sh` (add `E2E=1` for UI changes) |
| Every deploy | migrations first, then API, then web | chapter 10.6 |
| Weekly | read the logs for errors; check Neon compute use and the budget | Cloud Run → Logs (filter `severity>=ERROR`); Neon dashboard |
| Weekly | merge Dependabot updates that pass the gate | pull the branch, `scripts/check.sh`, merge |
| Monthly | dependency audit | `cd api && uv run pip-audit`; `cd web && npm audit --omit=dev` |
| Quarterly | restore drill | `docs/runbooks/restore.md` → "Drill"; write the date in its table |
| Yearly | rotate keys | 11.5 |

**GitHub Actions are off** (CI, CodeQL, Deploy) to save money. To switch one back on:
repository → **Actions** → the workflow → **Enable workflow**. On a private repository the
free 2,000 minutes a month cover roughly 100 full CI runs, so re-enabling CI alone is
usually still free.

## 11.2 Watching it

- **Logs:** Cloud Run writes JSON logs; each line has `request_id`, `tenant_id`,
  `user_id`. A user's error message shows the request id (`X-Request-Id`): search for it.
- **Errors:** optional Sentry (`SENTRY_DSN`; the free plan is enough).
- **Uptime:** a free monitor (Cloud Monitoring uptime check, or UptimeRobot) on
  `https://<your domain>/` and on the API's `/healthz` (not `/readyz`, which wakes the
  database).
- **Outbox health:** events that failed 8 times stay in `outbox_events` with `last_error`:
  `SELECT topic, last_error, attempts FROM outbox_events WHERE dispatched_at IS NULL ORDER BY created_at;`
- **Product use:** Settings → Platform (operators): counts per module, nothing personal.

## 11.3 Backups and restore

- **Neon point-in-time restore** is the first tool (minutes to restore; the window depends
  on the plan).
- **Nightly encrypted dumps** in R2, 30 days, readable only with your offline `age` key.
- Step by step: `docs/runbooks/restore.md` (whole database, one workspace, the drill).

## 11.4 Incidents

`docs/runbooks/incident.md`: confirm, contain (revoke keys/sessions, switch a feature off,
roll back), communicate (affected owners; the authority within 72 hours for a personal data
breach under the PDPO/GDPR), fix, write it up.

Rolling back the API: Cloud Run → `companymgmt-api` → Revisions → the previous one →
**Manage traffic → 100%**. Migrations are backward compatible, so the previous revision
works on the newer schema. The web: Cloudflare Pages → Deployments → an older one →
**Rollback**.

## 11.5 Rotating secrets

| Secret | How | Effect |
|---|---|---|
| `JWT_PRIVATE_KEY` | new key from `scripts/gen-keys.sh`, new secret version, redeploy | everyone's access token fails once and refreshes silently (refresh tokens are separate) |
| `FIELD_ENCRYPTION_KEYS` | add a new id (`{"k1": "…", "k2": "…"}`), set `FIELD_ENCRYPTION_ACTIVE_KID=k2`, redeploy; keep `k1` until old values are re-encrypted | new writes use k2; old values still decrypt |
| `INTERNAL_TOKEN` | new version, redeploy, update each scheduler job's header | jobs fail until updated |
| `PROXY_TOKEN` | set the new value in both Secret Manager and the Pages project, redeploy the API | a minute of 403s between the two |
| Database passwords | `ALTER ROLE … PASSWORD …` in Neon, new URL secrets, redeploy | — |
| SMTP / Gemini / R2 keys | new key at the provider, new secret version, redeploy | — |

## 11.6 Common admin tasks (until there's an admin screen)

Connect as `cm_owner` (Neon SQL editor or `psql "$MIGRATIONS_DATABASE_URL"`).

```sql
-- Find a workspace
SELECT id, name, slug, status, created_at FROM tenants WHERE name ILIKE '%tea%';

-- Change its plan (no billing yet). RLS applies to the owner too: choose the workspace first.
SELECT set_config('app.tenant_id', '<tenant id>', false);
UPDATE subscriptions SET plan_key = 'business', status = 'active', trial_ends_at = NULL
 WHERE tenant_id = '<tenant id>';

-- Who are the owners?
SELECT u.email FROM memberships m JOIN roles r ON r.id = m.role_id JOIN users u ON u.id = m.user_id
 WHERE m.tenant_id = '<tenant id>' AND r.key = 'owner';
```

Change AI allowances in the app (Settings → Platform), not in SQL, so workspaces are told.
Every change you make by hand should also be written down in an incident or admin log of
your own.

## 11.7 Upgrading things

- **Python packages:** `cd api && uv lock --upgrade && uv sync`, then the gate.
- **Node packages:** `cd web && npm update` (minor) or edit `package.json` (major), then the gate
  with `E2E=1`.
- **Postgres major version:** Neon supports in-place upgrades; try on a branch first.
- **Python / Node versions:** change `api/Dockerfile`, `pyproject.toml` (`requires-python`),
  the workflows' `node-version`, then the gate.

## 11.8 Making the repository private, and other owner-only settings

These need you in GitHub's settings (an automated session can't change them):

- **Private:** Settings → General → Danger zone → **Change visibility** → Private.
- **Actions:** Settings → Actions → General, or each workflow's **Disable/Enable**.
- **Dependabot:** Settings → Code security → Dependabot (free; keep it on).
- **Branch protection** is optional for a single maintainer; the local gate is the rule.
