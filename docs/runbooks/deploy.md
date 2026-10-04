# Deploying CompanyMgmt (first time)

About an hour, once. After this every push to `main` that passes CI deploys itself.
Everything here is free until there's real usage (see the plan, §7.4). You never need to
share passwords with anyone: each step says exactly where to paste what.

What you'll create:

| Service | For | Cost at 0 users |
|---|---|---|
| Neon | Postgres database | $0 (Free plan) |
| Google Cloud | Runs the API (Cloud Run), stores secrets | $0 (free tier) |
| Cloudflare | Hosts the web app and site (one static project) and forwards `/v1` to the API, DNS | $0 |
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
   -- Reads everything for the nightly backup; can change nothing.
   CREATE ROLE cm_backup LOGIN BYPASSRLS PASSWORD 'BACKUP-PASSWORD-HERE';
   GRANT cm_app TO cm_owner;
   CREATE DATABASE companymgmt OWNER cm_owner;
   ```

   Then switch the SQL Editor to database `companymgmt` and run:

   ```sql
   GRANT USAGE ON SCHEMA public TO cm_backup;
   ALTER DEFAULT PRIVILEGES FOR ROLE cm_owner IN SCHEMA public GRANT SELECT ON TABLES TO cm_backup;
   ALTER DEFAULT PRIVILEGES FOR ROLE cm_owner IN SCHEMA public GRANT SELECT ON SEQUENCES TO cm_backup;
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
   - With **Connection pooling OFF**, copy the address for role `cm_backup` → the
     **backup URL**. Keep it starting with `postgresql://` (it's used by `pg_dump`).

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
   gcloud secrets versions add backup-database-url --data-file=-     # the backup URL
   ```

   **Back up `field-encryption-keys` somewhere safe** (a password manager). Without it,
   encrypted fields such as national ID numbers can't be read.

## 3. Cloudflare

1. Sign up at <https://dash.cloudflare.com>. (If you have a domain: **Add a site** and
   follow the steps to move its DNS to Cloudflare.)
2. **Workers & Pages → Create → Pages → Direct upload**: create one project named
   `companymgmt`. (Upload anything; the first real deploy replaces it.) It serves the site,
   the app, and `/v1/*` through a small function that forwards to the API, so the sign-in
   cookie stays on your web address.
3. Make the proxy secret (any long random value) and store it in both places:
   ```bash
   openssl rand -base64 32 | tr -d '\n' > proxy-token.txt
   gcloud secrets versions add proxy-token --data-file=proxy-token.txt
   ```
   Then in the Pages project → **Settings → Variables and secrets**, add
   `PROXY_TOKEN` (type *Secret*, the same value) and, after the first API deploy (step 6),
   `API_ORIGIN` = the Cloud Run URL. Delete `proxy-token.txt` afterwards.
4. **My Profile → API Tokens → Create token → Custom token**:
   - Permissions: *Account → Cloudflare Pages → Edit* (only this).
   - Account resources: your account. Create it and copy the token.
5. Note your **Account ID** (Workers & Pages overview, right side).
6. Optional, for spam protection on sign-in: **Turnstile → Add widget** for your app
   domain. Copy the *site key* (public) and *secret key*; add the secret to Google:
   `gcloud secrets create turnstile-secret --replication-policy=user-managed --locations=asia-southeast1`
   then `gcloud secrets versions add turnstile-secret --data-file=-`, and add
   `TURNSTILE_SECRET=turnstile-secret:latest` to `--set-secrets` in `deploy.yml`.

7. Optional, the AI assistant (Gemini): in [Google AI Studio](https://aistudio.google.com/apikey)
   create an API key **in a project with billing switched on** (on the free tier Google
   may use prompts to improve its products, which the in-app terms don't allow). Add it:
   `gcloud secrets create gemini-api-key --replication-policy=user-managed --locations=asia-southeast1`,
   then `gcloud secrets versions add gemini-api-key --data-file=-`, and add
   `GEMINI_API_KEY=gemini-api-key:latest` to `--set-secrets` in `deploy.yml`. That's all:
   the assistant switches itself on, and each workspace's owner still chooses to use it.
   Set `PLATFORM_OPERATORS` (your email, with two-step sign-in on) to change how many
   questions each plan includes, under Settings → Platform.

8. **Backups (R2)**: **R2 → Create bucket** `companymgmt-backups` (location: Asia
   Pacific). Then **R2 → Manage API tokens → Create API token**: *Object Read & Write*,
   only that bucket. Note the *Access Key ID*, *Secret Access Key* and the *S3 endpoint*
   (`https://<account-id>.r2.cloudflarestorage.com`), and add the keys to Google:

   ```bash
   gcloud secrets versions add r2-access-key-id --data-file=-
   gcloud secrets versions add r2-secret-access-key --data-file=-
   ```

   Make the backup encryption key **on your own computer** (`age-keygen -o backup-key.txt`,
   from <https://age-encryption.org>). The line starting `age1…` is the public key: it goes
   into GitHub (step 5). The file itself is the only way to read a backup: keep it in a
   password manager and on paper, never in the cloud account.

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
| Variable | `CLOUDFLARE_ACCOUNT_ID` | from step 3.5 |
| Variable | `WEB_URL` | `https://companymgmt.pages.dev` (or `https://yourdomain`) |
| Variable | `MAIL_FROM` | `CompanyMgmt <no-reply@yourdomain>` |
| Variable | `TURNSTILE_SITE_KEY` | optional, from step 3.6 |
| Secret | `CLOUDFLARE_API_TOKEN` | from step 3.4 |
| Variable | `BACKUP_AGE_RECIPIENT` | the `age1…` public key from step 3.8 |
| Variable | `R2_BACKUP_BUCKET` | `companymgmt-backups` |
| Variable | `R2_ENDPOINT` | `https://<account-id>.r2.cloudflarestorage.com` |
| Variable | `DEPLOY_ENABLED` | `true` (last) |

## 6. First deploy

**Actions → Deploy → Run workflow**. When it finishes:

1. `gcloud run services describe companymgmt-api --region asia-southeast1 --format 'value(status.url)'`
   prints the API address. Add it as `API_ORIGIN` in the Pages project's variables
   (step 3.3). No redeploy is needed: the function reads it on each request. From then on
   the API answers `/v1` only through the web address.
2. Scheduled jobs (retries for emails, daily clean-up, the daily email summary):

   ```bash
   API=$(gcloud run services describe companymgmt-api --region asia-southeast1 --format 'value(status.url)')
   TOKEN=$(gcloud secrets versions access latest --secret internal-token)
   gcloud scheduler jobs create http companymgmt-outbox --location asia-southeast1 \
     --schedule "*/10 * * * *" --uri "$API/internal/outbox/dispatch" --http-method POST \
     --headers "X-Internal-Token=$TOKEN"
   gcloud scheduler jobs create http companymgmt-daily --location asia-southeast1 \
     --schedule "17 3 * * *" --uri "$API/internal/maintenance/daily" --http-method POST \
     --headers "X-Internal-Token=$TOKEN"
   # The daily email summary of unread notifications, at 8:52 in the morning in Dhaka.
   gcloud scheduler jobs create http companymgmt-digest --location asia-southeast1 \
     --schedule "52 8 * * *" --time-zone "Asia/Dhaka" --uri "$API/internal/notifications/digest" \
     --http-method POST --headers "X-Internal-Token=$TOKEN"
   # Weekly and monthly reports people asked for by email (sent on the first day of the
   # week or month in each workspace's time zone; safe to run more than once a day).
   gcloud scheduler jobs create http companymgmt-reports --location asia-southeast1 \
     --schedule "37 7 * * *" --time-zone "Asia/Dhaka" --uri "$API/internal/reports/send" \
     --http-method POST --headers "X-Internal-Token=$TOKEN"
   ```

3. The nightly jobs (`companymgmt-maintenance` purges deleted workspaces and old audit
   entries; `companymgmt-backup` writes the encrypted dump) are scheduled by OpenTofu.
   Run each once now to check them:

   ```bash
   gcloud run jobs execute companymgmt-maintenance --region asia-southeast1 --wait
   gcloud run jobs execute companymgmt-backup --region asia-southeast1 --wait
   ```

   The backup's log ends with `{"backup": "companymgmt-….dump.age", …}`, and the file
   appears in the R2 bucket under `db/`.
4. Check: open the web app, sign up, confirm the email arrives, clock in on your phone.

## Custom domain (later)

- Cloudflare → the `companymgmt` Pages project → **Custom domains** → add `yourdomain`.
  The API needs no domain of its own: it is reached through `/v1` on the same address.
  Update `WEB_URL` and redeploy.

## Rolling back

Cloud Run keeps earlier revisions: **Cloud Run → companymgmt-api → Revisions → (older
revision) → Manage traffic → 100%**. Migrations are written to be backward compatible,
so the previous revision works with the newer schema.
