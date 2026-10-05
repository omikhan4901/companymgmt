# 10. Production at the lowest cost

The whole stack scales to zero. With no customers it costs **about $1 a month** (the
domain); with the first few dozen small workspaces it stays inside free tiers. This chapter
explains what you need, what it costs, the cheapest settings, and what makes the bill grow.
The click-by-click setup is `docs/runbooks/deploy.md` (about an hour, once).

Prices below are the providers' published free tiers and rates as best known in October
2026. They change: check each pricing page before you rely on a number.

## 10.1 What you need

| Service | For | Free tier that matters | Cost at 0 users |
|---|---|---|---|
| **Domain** (Cloudflare Registrar, at cost) | `companymgmt.app` or similar | — | ~$12–15 / year |
| **Cloudflare** (Free plan) | DNS, TLS, WAF, Pages (site + app), the `/v1` Pages Function, Turnstile | Pages: unlimited static requests; Functions: 100,000 requests/day | $0 |
| **Cloudflare R2** | encrypted nightly backups | 10 GB storage, no egress fees | $0 |
| **Google Cloud Run** | the API, migrations, nightly jobs | per month: 2 million requests, 180,000 vCPU-seconds, 360,000 GiB-seconds | $0 |
| **Artifact Registry** | the API image | 0.5 GB (the cleanup policy keeps 5 images) | $0 |
| **Secret Manager** | keys and URLs | 6 active secret versions free, then ~$0.06 each / month | ~$0.30 |
| **Cloud Scheduler** | calls the jobs | 3 jobs per billing account, then $0.10 / job / month | ~$0.50 |
| **Neon** (Free plan) | Postgres 16 in Singapore | one project, 0.5 GB storage, a monthly compute allowance, scale to zero after 5 idle minutes, short point-in-time history | $0 |
| **Resend** (or any SMTP) | email | 3,000 emails / month, 100 / day | $0 |
| **Gemini** (optional) | the AI assistant | pay per use; **must be a paid-tier key** (the free tier may train on prompts, which the terms forbid) | $0 until used |
| **GitHub** (Free, private repo) | the code | Actions: 2,000 minutes / month on private repos | $0 |

**Total at launch: about $1–2 a month.**

## 10.2 The one thing that silently costs money: waking the database

Neon bills (or counts against the free allowance) the **time its compute is awake**. It
sleeps after 5 idle minutes and wakes on any query. Cloud Run likewise only bills while
handling requests. So every scheduled job that touches the database keeps Neon awake for
about 5 minutes.

- A job **every minute** keeps Neon awake all month (~730 hours) — that alone exceeds the
  free allowance.
- A job every 15 minutes keeps it awake about a third of the time.
- A job every 30 minutes, about a sixth.

So the cheapest schedule **aligns jobs on the same minutes** (one wake serves them all)
and runs them as rarely as the product allows (10.3).

Likewise, point uptime monitors at `/healthz` (no database), never `/readyz`.

## 10.3 The cheapest schedule

| Job | Cheapest sensible schedule | Why that's enough |
|---|---|---|
| `companymgmt-outbox` → `/internal/outbox/dispatch` | `*/30 * * * *` | only retries: normal delivery happens during each request (`FlushMiddleware`) |
| `companymgmt-automations` → `/internal/automations/tick` | `*/30 * * * *` | scheduled automations are daily/weekly; half an hour late is fine |
| `companymgmt-webhooks` → `/internal/webhooks/tick` | **don't create it** until a Business customer uses webhooks; then `*/30` to start, `* * * * *` only if they need near-real-time | webhooks need the Business plan |
| `companymgmt-daily` → `/internal/maintenance/daily` | `17 3 * * *` | once a day |
| `companymgmt-digest` → `/internal/notifications/digest` | `52 8 * * *` Asia/Dhaka | once a day, morning |
| `companymgmt-reports` → `/internal/reports/send` | `37 7 * * *` Asia/Dhaka | once a day; sends only on week/month starts |
| `companymgmt-maintenance`, `companymgmt-backup` (Cloud Run jobs, created by OpenTofu) | nightly | already set |

Use the exact same minute pattern (`*/30`) for outbox and automations so they wake Neon
together. When customers start using the product during the day, their own requests keep
Neon awake anyway, and the jobs cost nothing extra. Commands to create the jobs are in
`docs/runbooks/deploy.md` §6 — replace its `*/10` and `*/15` with `*/30`, and skip the
webhooks job until you need it.

## 10.4 Cheapest Cloud Run settings (already in the deploy commands)

- `--min-instances 0`: nothing runs when nobody uses it (a cold start takes a few seconds
  for the first request).
- `--max-instances 4`: caps the bill and protects the database's connection limit.
- `--concurrency 40 --cpu 1 --memory 512Mi`: one small instance serves a lot of people.
- Request-based billing (the default): you pay only while requests run.
- Region `asia-southeast1` (Singapore), the same as Neon, so queries don't cross oceans.

## 10.5 Going live, in order

The detail for each step is in `docs/runbooks/deploy.md`.

1. **Neon**: create the project (Postgres 16, Singapore) and the three roles with SQL.
   Copy the pooled `cm_app` URL, the direct `cm_owner` URL and the `cm_backup` URL.
2. **Google Cloud**: a project with billing linked; `tofu apply` in `infra/gcp` creates the
   image registry (with cleanup), service accounts, secrets, the GitHub deploy identity, a
   **budget alert** (set `billing_account` and `monthly_budget_usd`, e.g. 10), and the
   nightly job schedules.
3. **Secrets**: `scripts/gen-keys.sh` prints the JWT key, the field-encryption keys and the
   internal token; add them and the database URLs and SMTP URL to Secret Manager.
   **Keep `FIELD_ENCRYPTION_KEYS` in your password manager**: without it encrypted fields
   can't be read, and a restore is useless.
4. **Cloudflare**: a Pages project `companymgmt`; `PROXY_TOKEN` (secret) and `API_ORIGIN`
   variables; your domain; optionally Turnstile.
5. **R2** bucket for backups and an `age` key pair made on your computer (the private key
   never goes to the cloud).
6. **Email**: Resend domain verification (DNS records in Cloudflare), SMTP URL secret.
7. **Deploy** (10.6).
8. **Scheduler jobs** (10.3).
9. **Check**: sign up, receive the email, clock in on your phone, run the backup job once
   and see the file in R2, do a restore drill (`docs/runbooks/restore.md`).

## 10.6 Deploying with GitHub Actions switched off

The repository's workflows are disabled to save money. You have two options.

**Option A — run the Deploy workflow by hand (still free).** Private repositories on
GitHub Free get 2,000 Actions minutes a month; a deploy takes about 6–8 minutes. Enable
only **Actions → Deploy** (leave CI and CodeQL off), and start it with **Run workflow**
after `scripts/check.sh` passes locally. Its trigger on CI completion won't fire while CI
is off, so it only runs when you click. This is the easiest path.

**Option B — deploy from your computer** (needs Docker, `gcloud`, and Node). The same
steps the workflow runs:

```bash
REGION=asia-southeast1; PROJECT=companymgmt-prod
IMAGE=$REGION-docker.pkg.dev/$PROJECT/companymgmt/api:$(git rev-parse --short HEAD)
RUNTIME_SA=companymgmt-run@$PROJECT.iam.gserviceaccount.com
SECRETS=DATABASE_URL=database-url:latest,JWT_PRIVATE_KEY=jwt-private-key:latest,FIELD_ENCRYPTION_KEYS=field-encryption-keys:latest,SMTP_URL=smtp-url:latest

scripts/check.sh                                         # never deploy what doesn't pass
gcloud auth configure-docker $REGION-docker.pkg.dev
docker build -f api/Dockerfile -t $IMAGE . && docker push $IMAGE

# 1. migrations (a one-off Cloud Run job)
gcloud run jobs deploy companymgmt-migrate --region $REGION --image $IMAGE \
  --service-account $RUNTIME_SA --command alembic --args upgrade,head \
  --set-env-vars ENV=prod,EMAIL_BACKEND=smtp,APP_DB_ROLE=cm_app \
  --set-secrets MIGRATIONS_DATABASE_URL=migrations-database-url:latest,$SECRETS \
  --max-retries 0 --task-timeout 600
gcloud run jobs execute companymgmt-migrate --region $REGION --wait

# 2. the nightly maintenance job uses the same image
gcloud run jobs deploy companymgmt-maintenance --region $REGION --image $IMAGE \
  --service-account $RUNTIME_SA --command python --args=-m,app.jobs.maintenance \
  --set-env-vars ENV=prod,APP_DB_ROLE=cm_app \
  --set-secrets MIGRATIONS_DATABASE_URL=migrations-database-url:latest,$SECRETS \
  --max-retries 1 --task-timeout 1800

# 3. the API
WEB=https://companymgmt.app
gcloud run deploy companymgmt-api --region $REGION --image $IMAGE \
  --service-account $RUNTIME_SA --allow-unauthenticated --ingress all \
  --min-instances 0 --max-instances 4 --concurrency 40 --cpu 1 --memory 512Mi \
  --set-env-vars "ENV=prod,EMAIL_BACKEND=smtp,APP_DB_ROLE=cm_app,WEB_BASE_URL=$WEB,CORS_ORIGINS=$WEB,MAIL_FROM=CompanyMgmt <no-reply@companymgmt.app>" \
  --set-secrets $SECRETS,INTERNAL_TOKEN=internal-token:latest,PROXY_TOKEN=proxy-token:latest
curl -f "$(gcloud run services describe companymgmt-api --region $REGION --format 'value(status.url)')/readyz"

# 4. the web app
cd web && npm ci && NEXT_PUBLIC_SITE_URL=$WEB NEXT_TELEMETRY_DISABLED=1 npm run build
npx wrangler pages deploy out --project-name companymgmt --branch main   # `npx wrangler login` once
```

Add `,GEMINI_API_KEY=gemini-api-key:latest` (and `TURNSTILE_SECRET`) to the API's
`--set-secrets` when you use them, `PLATFORM_OPERATORS=you@…` to its env vars, and
`NEXT_PUBLIC_TURNSTILE_SITE_KEY` to the web build. The backup job is built from
`infra/backup/Dockerfile` the same way (see `.github/workflows/deploy.yml`, job step
"Build and deploy the nightly backup job"). These commands mirror the workflow but have
not been run against a real project yet.

## 10.7 What makes the bill grow, and when to act

| Signal | What happens | What to do |
|---|---|---|
| Neon compute allowance used up | the database is suspended until next month on Free | Neon's paid plan (usage-based, a few dollars at small scale); or slow the jobs (10.3) |
| Neon storage > 0.5 GB | writes refused on Free | paid plan. Documents' files and receipt photos live in Postgres; move them to R2 when storage grows (a code change in `documents/` and `expenses/`) |
| Cloud Run beyond the free tier | pennies per extra million requests | nothing until hundreds of active workspaces |
| More than ~100 emails a day | Resend Free stops for the day | Resend's paid tier (~$20/month), or turn the daily digest off by default |
| Gemini use | billed per token | allowances per plan cap it; check usage under Settings → Platform |
| A busy workspace makes reports slow | reports are computed per request | stored daily totals (a code change) |
| Point-in-time restore window too short (Free: hours) | less safety | Neon paid plan gives days; nightly R2 dumps cover 30 days meanwhile |

Set the **budget alert** (OpenTofu `monthly_budget_usd`, e.g. $10) so you hear about a
change before it costs much, and look at the Neon dashboard's compute usage in the first
week.

## 10.8 A rough path as it grows

| Stage | Monthly cost | What changes |
|---|---|---|
| Launch, no customers | ~$1–2 | everything on free tiers |
| First 5–20 small workspaces | ~$1–5 | maybe the Neon paid plan if compute runs out |
| 50–100 workspaces | ~$25–60 | Neon paid, Resend paid, Gemini usage |
| Larger | grows with use | consider files on R2, stored report totals, a second region, read replicas |

Revenue at that point (Starter $9, Growth $29) covers it many times over — once billing
(M5) exists.
