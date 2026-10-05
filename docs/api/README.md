# CompanyMgmt API

The same API the web app uses, opened up for your own systems: payroll exports, HR
integrations, BI dashboards, point-of-sale bridges. Available on the **Business** and
**Enterprise** plans; SCIM provisioning and company sign-in need **Enterprise**.

- Base URL: `https://companymgmt.app/v1` (the API is served through the web address).
- Reference: the OpenAPI document at `/v1/openapi.json` (the published contract is
  [`openapi-v1.json`](openapi-v1.json) in this folder).
- Everything is JSON over HTTPS. Times are ISO 8601 in UTC. Money is an **integer in
  minor units** (৳115.00 is `11500`). Quantities and percentages are decimal strings.

## 1. Authentication: API keys

Make a key in **Settings → Developers → API keys** (owner or admin; permission
`developers.manage`). Choose exactly the permissions it needs. You see the key once:

```
cmk_<workspace id>_<secret>
```

Send it as a bearer token:

```bash
curl https://companymgmt.app/v1/members -H "Authorization: Bearer $CM_KEY"
```

How keys behave:

| | |
|---|---|
| Acts as | the person who made it, limited to the key's permissions. If that person is demoted, the key shrinks with them; if they leave, the key stops (`401 api_key_owner_gone`). |
| Never | owner-only powers (billing, deleting the workspace), account routes (`/v1/auth/*`), making other keys. |
| Rate limit | per key, per minute (10–1200, default 120). Over it: `429` with `Retry-After`. |
| Networks | optionally tied to CIDR ranges (`allowed_ips`); elsewhere: `403 ip_not_allowed`. |
| Expiry | 1–730 days, or never. |
| Rotation | `POST /v1/api-keys/{id}/rotate` with `grace_hours` (0–168): the old secret keeps working that long, so you can deploy the new one without downtime. |
| Usage | `GET /v1/api-keys/{id}/usage?days=30`: requests and writes per day. Last use time and address are on the key. |

Store keys in a secret manager. Revoke a leaked key at once (`DELETE /v1/api-keys/{id}`).

## 2. Errors

Errors are [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) problem documents
(`application/problem+json`):

```json
{
  "type": "https://companymgmt.app/problems/validation",
  "title": "Check the highlighted fields",
  "status": 422,
  "detail": "Check the highlighted fields",
  "code": "validation",
  "errors": [{"field": "email", "message": "Enter a valid email address."}],
  "request_id": "6f1c0a2b9d3e4f51"
}
```

Branch on `status` and the stable `code`, not on the wording (it may be translated). Quote
`request_id` when asking for help.

| Status | Typical `code` | Meaning |
|---|---|---|
| 400 | `bad_request`, `idempotency_key_invalid` | malformed request |
| 401 | `unauthorized`, `api_key_invalid` | missing, wrong, expired or revoked credentials |
| 402 | `api_not_in_plan`, `module_off`, `workspace_read_only` | the plan or a switched-off module doesn't allow it |
| 403 | `forbidden`, `ip_not_allowed`, `sso_required` | the key/person may not do this |
| 404 | `not_found` | doesn't exist **in this workspace** |
| 409 | `conflict`, `version_conflict`, `idempotency_in_progress` | state changed; re-read and retry |
| 412/428 | `version_conflict` / `if_match_required` | see §4 |
| 422 | `validation`, `idempotency_key_reused` | fix the request |
| 429 | `too_many_requests` | slow down; honour `Retry-After` |
| 5xx | | our fault; retry with backoff (and an Idempotency-Key for writes) |

## 3. Pagination

Long lists return `{"items": [...], "next_cursor": "..."}`. Pass `cursor=<next_cursor>`
for the next page until it's `null`. `limit` is usually 1–200. Cursors are opaque.

## 4. Editing safely: versions (ETag / If-Match)

Records people edit carry a `version`. Updates require `If-Match: W/"<version>"`; if
someone changed it since you read it you get `412 version_conflict` instead of silently
overwriting their change. Re-read, re-apply, retry.

## 5. Retrying writes: Idempotency-Key

Add `Idempotency-Key: <unique string>` (up to 200 printable ASCII characters, e.g. a UUID)
to any `POST`, `PUT`, `PATCH` or `DELETE`. Send the same request again with the same key
(after a timeout, say) and you get the first response back, with
`Idempotent-Replayed: true`, instead of doing the work twice.

- Keys belong to your API key, last 24 hours, and must be used for the same request
  (same method, path, query and body), else `422 idempotency_key_reused`.
- While the first request is still running, a retry gets `409 idempotency_in_progress`.
- Server errors (5xx) aren't remembered, so a retry runs again.

## 6. Webhooks

Get told when things happen instead of polling. **Settings → Developers → Webhooks**, or
`POST /v1/webhooks` with an `https://` URL and the events you want (`["*"]` for all).
`GET /v1/webhooks/events` lists the catalogue:

| Event | When | `data` |
|---|---|---|
| `employee.onboarded` | someone joined the workspace | `membership_id` |
| `employee.offboarded` | someone was removed | `membership_id` |
| `leave.requested` / `leave.approved` | leave asked for / approved | `employee_id`, `membership_id`, `start_date`, `end_date`, `days` |
| `leave.rejected` / `leave.cancelled` | | `employee_id`, `membership_id` |
| `attendance.corrected` | an attendance correction was approved | |
| `task.assigned` | | |
| `document.published` / `announcement.published` | | |
| `payroll.finalized` | a pay run was finalised | `period`, `headcount` |
| `sale.completed` / `sale.returned` / `sale.voided` | | `number`, `total`, `customer_id` / `original_id`, `total` / `number` |
| `drawer.closed` | a cash drawer was closed | |
| `customer.paid` | a customer paid towards dues | `amount` |
| `expense.recorded` | | `amount`, `category_id` |
| `purchase.received` / `supplier.paid` | | `total`, `paid`, `supplier_id` / `supplier_id`, `amount` |
| `stock.low` | an item reached its reorder level | `quantity`, `reorder_level` |
| `ping` | the **Send test** button | |

Every delivery is a `POST` like this:

```json
{
  "id": "0192f3c1-...",              // the event id: the same on retries and resends
  "type": "leave.approved",
  "created_at": "2026-10-05T09:12:44+00:00",
  "workspace_id": "0192...",
  "subject": {"type": "leave_request", "id": "0192..."},
  "data": {"employee_id": "...", "days": "2.0", "start_date": "2026-10-12", "end_date": "2026-10-13"}
}
```

Payloads are deliberately thin: ids and a few plain fields, **never** names, notes,
salaries or contact details. Fetch details with your API key, which checks permissions.

### Verify the signature

Each request carries `CompanyMgmt-Signature: t=<unix seconds>,v1=<hex>`, where `v1` is the
HMAC-SHA256 of `"<t>.<raw body>"` with the endpoint's signing secret (`whsec_...`, shown
once; roll it with `POST /v1/webhooks/{id}/secret`). Check it against the **raw** body
and refuse anything older than 5 minutes:

```python
import hashlib, hmac, time

def verify(secret: str, body: bytes, header: str, tolerance: int = 300) -> bool:
    parts = dict(item.split("=", 1) for item in header.split(","))
    t = int(parts["t"])
    if abs(time.time() - t) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts.get("v1", ""))
```

```js
import crypto from "node:crypto";
export function verify(secret, rawBody, header, tolerance = 300) {
  const parts = Object.fromEntries(header.split(",").map((p) => p.split("=")));
  const t = Number(parts.t);
  if (Math.abs(Date.now() / 1000 - t) > tolerance) return false;
  const expected = crypto.createHmac("sha256", secret).update(`${t}.`).update(rawBody).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(parts.v1 ?? ""));
}
```

Both SDKs ship this as `verifyWebhook`.

### Delivery rules

- Deliveries go out within about a minute of the event (a slow receiver never holds up
  the change in CompanyMgmt). **Send test** and **Resend** go out at once.
- Answer `2xx` within 10 seconds; do slow work afterwards. Redirects aren't followed.
- Anything else is retried after 1 min, 5 min, 30 min, 2 h, 6 h, 12 h and 24 h (8 tries).
  After 40 failures in a row the endpoint is switched off; fix it and switch it back on.
- Deliveries can arrive more than once and out of order: de-duplicate on `id`.
- The delivery log (`GET /v1/webhooks/{id}/deliveries`) shows each attempt's status and
  timing; **Resend** (`POST /v1/webhooks/deliveries/{id}/resend`) sends it again now.
- We only send to public internet addresses over HTTPS (ports 443 or 8443).

## 7. Sandbox

`POST /v1/workspace/sandbox` (owner) makes a separate workspace, "<name> (sandbox)", with
the same plan features and never billed. Switch to it from the workspace menu, add sample
data from its first-day checklist, and point your integration at it with a key made
there. One sandbox per workspace; delete it like any workspace.

## 8. Company sign-in (OpenID Connect SSO)

Enterprise plan. **Settings → Security → Company sign-in** (owner). You need the
provider's **issuer**, a **client id and secret**, and your email **domains**. Register
this redirect address at the provider (also shown on the settings page):

```
https://companymgmt.app/sso/callback
```

Options: **auto-join** (people from your domains get an account on first sign-in, with
the default role), **require company sign-in** (everyone except the owner and staff
without an email must use it; checked on every request, so open sessions are cut off).

### Google Workspace

1. Google Cloud console → APIs & Services → Credentials → Create credentials → OAuth
   client ID → Web application.
2. Authorised redirect URI: the address above. Consent screen: Internal.
3. Issuer: `https://accounts.google.com`. Paste the client id and secret.

### Microsoft Entra ID

1. Entra admin centre → App registrations → New registration; redirect URI (Web): the
   address above.
2. Certificates & secrets → New client secret.
3. Issuer: `https://login.microsoftonline.com/<tenant id>/v2.0`. Under Token
   configuration add the optional `email` claim.

### Okta

1. Applications → Create App Integration → OIDC → Web Application; sign-in redirect URI:
   the address above; grant type Authorization Code.
2. Issuer: `https://<your-org>.okta.com` (or your custom authorisation server).

## 9. SCIM provisioning

Enterprise plan. Your identity provider adds people when they're hired and removes them
when they leave.

1. Make an API key with **members.view, members.invite and members.manage**.
2. In the provider: SCIM base URL `https://companymgmt.app/v1/scim/v2`, authentication
   "HTTP header / bearer token" with the key.
3. Supported: `Users` (list with `filter=userName eq "..."` / `externalId eq "..."`,
   create, replace, PATCH `active`/`displayName`/`externalId`, delete). Groups aren't yet.

A SCIM user is a membership: `active: false` or `DELETE` removes the person from the
workspace and ends their sessions (their history stays); `active: true` brings them back.
New people get the company sign-in's default role. The owner can't be changed over SCIM.

- **Okta:** create a SAML/OIDC app or "SCIM 2.0 Test App (Header Auth)", enable
  provisioning: Create Users, Update User Attributes, Deactivate Users.
- **Entra ID:** Enterprise applications → your app → Provisioning → Automatic; Tenant URL
  and Secret Token as above; map `userPrincipalName` or `mail` to `userName`.

## 10. Other enterprise controls

- **Network allowlist** (Enterprise, owner): `PUT /v1/workspace/ip-allowlist` with CIDR
  ranges. People and keys outside them get `403 ip_not_allowed`. You can't save a list
  that leaves your current address out.
- **Audit log export:** `GET /v1/audit/export?from=YYYY-MM-DD&to=YYYY-MM-DD&format=jsonl|csv`
  (permission `audit.view`). Each entry carries `prev_hash` and `hash`: the log is a hash
  chain, so you can prove nothing was removed or changed (`GET /v1/audit/verify`).
- **Your own AI key** (Enterprise, owner): `PUT /v1/ai/own-key` with a Gemini API key. The
  workspace's AI then runs on your Google account and our monthly allowance no longer
  applies.

## 11. Versioning and deprecation policy

- `/v1` is stable. Within it we only **add**: new operations, new optional request fields,
  new response fields, new enum values in requests, new webhook events and fields. Write
  clients that ignore fields they don't know.
- A breaking change (removing or renaming anything, making a field required, changing a
  type) never happens silently. We first **deprecate**: the old behaviour keeps working
  and responses carry `Deprecation: true`, `Sunset: <date>` and a `Link` to the
  replacement, for **at least 6 months** (12 for SCIM), announced in the changelog and by
  email to workspace owners with active keys. After the sunset date it may go away. Truly
  incompatible redesigns would be `/v2`, run side by side with `/v1`.
- Every build runs `python -m scripts.api_contract check`, which compares the app against
  [`openapi-v1.json`](openapi-v1.json) and fails on any breaking change. Updating the
  snapshot (`accept`) is a deliberate step taken only after the deprecation period.
- Routes under `/v1/auth`, `/v1/sso`, `/v1/public`, `/v1/join` and `/v1/operator` serve the
  web app and aren't part of the promise.

## 12. SDKs

Small, dependency-light clients live in [`/sdk`](../../sdk):

- **TypeScript** (`sdk/typescript`): `new CompanyMgmt({ apiKey })`, typed from the OpenAPI
  contract, automatic retries with Idempotency-Keys, pagination helper, `verifyWebhook`.
- **Python** (`sdk/python`): `CompanyMgmt(api_key=...)` on httpx, the same features.

```ts
import { CompanyMgmt, verifyWebhook } from "@companymgmt/sdk";
const cm = new CompanyMgmt({ apiKey: process.env.CM_KEY! });
for await (const member of cm.paginate("/members")) console.log(member.name);
await cm.post("/branches", { name: "Uttara" }); // retried safely with an Idempotency-Key
```

```python
from companymgmt import CompanyMgmt, verify_webhook
cm = CompanyMgmt(api_key=os.environ["CM_KEY"])
for member in cm.paginate("/members"):
    print(member["name"])
```

## 13. Provisioning recipes

Hiring and leaving, wired up end to end:

- **GitHub:** subscribe a small function (Cloudflare Worker, AWS Lambda, Cloud Run) to
  `employee.onboarded` / `employee.offboarded`. On onboard, read the person
  (`GET /v1/members/{membership_id}` with your key), then invite them to your GitHub
  organisation (`POST /orgs/{org}/invitations` with their email). On offboard, remove
  them (`DELETE /orgs/{org}/members/{username}`); keep the email→username map in your
  function's storage. Verify our signature first.
- **AWS IAM Identity Center:** prefer SCIM from your identity provider straight to AWS.
  Without one: on `employee.onboarded`, `identitystore:CreateUser` +
  `CreateGroupMembership`; on `employee.offboarded`, `DeleteUser`.
- **Google Workspace:** on `employee.onboarded`, Admin SDK Directory API
  `users.insert` (primaryEmail from the member record; a random first password with
  `changePasswordAtNextLogin`); on `employee.offboarded`, `users.update` with
  `suspended: true` (keep data) and transfer Drive files with the Data Transfer API.

Each recipe is idempotent if you de-duplicate on the event `id` and treat "already
exists" / "not found" as success.
