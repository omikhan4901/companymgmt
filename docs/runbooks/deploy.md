# Deploying CompanyMgmt (first time)

About an hour, once. After this every push to `main` that passes CI deploys itself.
Everything here is free until there's real usage (see the plan, §7.4). You never need to
share passwords with anyone: each step says exactly where to paste what.

What you'll create:

| Service | For | Cost at 0 users |
|---|---|---|
| Neon | Postgres database | $0 (Free plan) |
| Google Cloud | Runs the API (Cloud Run), stores secrets | $0 (free tier) |
| Cloudflare | Hosts the web app and the site, DNS | $0 |
| Resend (or any SMTP) | Sends emails | $0 (free tier) |
| A domain (optional now) | e.g. `companymgmt.app` | ~$12/year |

Without a domain you can use the free addresses (`*.run.app`, `*.pages.dev`) and add a
domain later.

---

## 1. Database: Neon

1. Sign up at <https://neon.com> → **Create project**.
   - Name: `companymgmt` · Postgres version: **16** · Region: **AWS Asia Pacific (Singapore)**.
2. Open **SQL Editor** (left menu) and run this, replacing the two passwords with long
   random ones (e.g. from a password manager):

   ```sql
   CREATE ROLE cm_owner LOGIN PASSWORD 'OWNER-PASSWORD-HERE';
   CREATE ROLE cm_app LOGIN NOBYPASSRLS PASSWORD 'APP-PASSWORD-HERE';
   GRANT cm_app TO cm_owner;
   CREATE DATABASE companymgmt OWNER cm_owner;
   ```

   Create `cm_app` with SQL like this, not in the Roles screen: roles made in the Neon
   console get extra privileges the app must not have.
3. Go to **Dashboard → Connect**. Choose database `companymgmt`.
   - With **Connection pooling ON**, copy the address for role `cm_app` → this is the
     **app URL**.
   - With **Connection pooling OFF**, copy the address for role `cm_owner` → this is the
     **migrations URL**.
   - Change each so it starts with `postgresql+psycopg://` and ends with
     `?sslmode=verify-full&sslrootcert=system`.

## 2. Google Cloud

1. <https://console.cloud.google.com> → project picker → **New project** `companymgmt-prod`.
   **Billing** → link your billing account (needed even for free-tier use).
2. Install the gcloud CLI (<https://cloud.google.com/sdk/docs/install>) and OpenTofu
   (<https://opentofu.org/docs/intro/install/>), then in a terminal:

   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project companymgmt-prod
   gcloud storage buckets create gs://companymgmt-prod-tofu-state --location=asia-southeast1 --uniform-bucket-level-access
   ```

3. In `infra/gcp`, copy `terraform.tfvars.example` to `terraform.tfvars`, set `project`
   (and `billing_account` for budget emails: **Billing → Account management**, the ID
   looks like `01ABCD-234567-89EFGH`). Uncomment the `backend "gcs"` block in `main.tf`
   with your bucket name, then:

   ```bash
   cd infra/gcp
   tofu init
   tofu apply
   ```

   Keep the four outputs; you'll paste them into GitHub in step 5.

4. Add the secret values (they never go into git or OpenTofu state). Generate keys first:

   ```bash
   scripts/gen-keys.sh   # prints JWT_PRIVATE_KEY, FIELD_ENCRYPTION_KEYS, INTERNAL_TOKEN
   ```

   Then add each value (paste it when the command waits, then press Ctrl-D):

   ```bash
   gcloud secrets versions add database-url --data-file=-            # the app URL from Neon
   gcloud secrets versions add migrations-database-url --data-file=- # the migrations URL
   gcloud secrets versions add jwt-private-key --data-file=-         # the PEM text, without quotes
   gcloud secrets versions add field-encryption-keys --data-file=-   # e.g. {"k1": "…"}
   gcloud secrets versions add internal-token --data-file=-
   gcloud secrets versions add smtp-url --data-file=-                # see step 4
   ```

   **Back up `field-encryption-keys` somewhere safe** (a password manager). Without it,
   encrypted fields such as national ID numbers can't be read.

## 3. Cloudflare

1. Sign up at <https://dash.cloudflare.com>. (If you have a domain: **Add a site** and
   follow the steps to move its DNS to Cloudflare.)
2. **Workers & Pages → Create → Pages → Direct upload**: create project
   `companymgmt-app`, then again for `companymgmt-site`. (Upload anything; the first real
   deploy replaces it.)
3. **My Profile → API Tokens → Create token → Custom token**:
   - Permissions: *Account → Cloudflare Pages → Edit* (only this).
   - Account resources: your account. Create it and copy the token.
4. Note your **Account ID** (Workers & Pages overview, right side).
5. Optional, for spam protection on sign-in: **Turnstile → Add widget** for your app
   domain. Copy the *site key* (public) and *secret key*; add the secret to Google:
   `gcloud secrets create turnstile-secret --replication-policy=user-managed --locations=asia-southeast1`
   then `gcloud secrets versions add turnstile-secret --data-file=-`, and add
   `TURNSTILE_SECRET=turnstile-secret:latest` to `--set-secrets` in `deploy.yml`.

## 4. Email

Any SMTP service works. With Resend: sign up, **Domains → Add domain** and add the DNS
records it shows (in Cloudflare DNS), then **API Keys → Create** (permission: *Sending
access*). The SMTP URL is `smtps://resend:API_KEY@smtp.resend.com:465`. Add it as the
`smtp-url` secret. `MAIL_FROM` becomes e.g. `CompanyMgmt <no-reply@yourdomain>`.

## 5. GitHub

Repository → **Settings → Environments → New environment** `production` (optionally
require your approval before each deploy). Then **Settings → Secrets and variables →
Actions**:

| Kind | Name | Value |
|---|---|---|
| Variable | `GCP_PROJECT` | `companymgmt-prod` |
| Variable | `GCP_REGION` | `asia-southeast1` |
| Variable | `GCP_WIF_PROVIDER` | output `workload_identity_provider` |
| Variable | `GCP_DEPLOY_SA` | output `deploy_service_account` |
| Variable | `GCP_RUNTIME_SA` | output `runtime_service_account` |
| Variable | `CLOUDFLARE_ACCOUNT_ID` | from step 3.4 |
| Variable | `WEB_URL` | `https://companymgmt-app.pages.dev` (or `https://app.yourdomain`) |
| Variable | `SITE_URL` | `https://companymgmt-site.pages.dev` (or `https://yourdomain`) |
| Variable | `API_URL` | leave empty for now; set after the first deploy (step 6) |
| Variable | `MAIL_FROM` | `CompanyMgmt <no-reply@yourdomain>` |
| Variable | `TURNSTILE_SITE_KEY` | optional, from step 3.5 |
| Secret | `CLOUDFLARE_API_TOKEN` | from step 3.3 |
| Variable | `DEPLOY_ENABLED` | `true` (last) |

## 6. First deploy

**Actions → Deploy → Run workflow**. When it finishes:

1. `gcloud run services describe companymgmt-api --region asia-southeast1 --format 'value(status.url)'`
   prints the API address. Set it as the `API_URL` variable and run **Deploy** again (the
   web app is built with it).
2. Scheduled jobs (retries for emails, daily clean-up):

   ```bash
   API=$(gcloud run services describe companymgmt-api --region asia-southeast1 --format 'value(status.url)')
   TOKEN=$(gcloud secrets versions access latest --secret internal-token)
   gcloud scheduler jobs create http companymgmt-outbox --location asia-southeast1 \
     --schedule "*/10 * * * *" --uri "$API/internal/outbox/dispatch" --http-method POST \
     --headers "X-Internal-Token=$TOKEN"
   gcloud scheduler jobs create http companymgmt-daily --location asia-southeast1 \
     --schedule "17 3 * * *" --uri "$API/internal/maintenance/daily" --http-method POST \
     --headers "X-Internal-Token=$TOKEN"
   ```

3. Check: open the web app, sign up, confirm the email arrives, clock in on your phone.

## Custom domain (later)

- Web app and site: Cloudflare → the Pages project → **Custom domains** → add
  `app.yourdomain` / `yourdomain`.
- API: `gcloud beta run domain-mappings create --service companymgmt-api --domain api.yourdomain --region asia-southeast1`,
  then add the DNS records it prints in Cloudflare with the proxy **off** (grey cloud).
  Update `API_URL`, `WEB_URL`, `SITE_URL` and redeploy.

## Rolling back

Cloud Run keeps earlier revisions: **Cloud Run → companymgmt-api → Revisions → (older
revision) → Manage traffic → 100%**. Migrations are written to be backward compatible,
so the previous revision works with the newer schema.
