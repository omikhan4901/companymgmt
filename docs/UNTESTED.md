# Test status

The speed-mode backlog (M7–M11, written 2026-10-04/05 with lint and type checks only) was
worked through on 2026-10-05. What ran, what it found, and what still can't be checked
from here.

## What ran and passes

| Suite | Result |
|---|---|
| API (pytest, real Postgres) | **321 passed**, 90% line and branch coverage (gate 85%) |
| Public API contract check | no breaking changes against `docs/api/openapi-v1.json` |
| Web unit tests (Vitest) | 35 passed |
| Web lint and types | clean |
| Static build | 43 pages with per-page security headers |
| Browser (Playwright, desktop) | 19 existing journeys passed |
| Browser, new (desktop and phone) | every new screen opens with no errors, no CSP breaks and no serious WCAG 2.2 AA findings; an API key is made and shown once; legal and security pages; a shop adds an item, sells it at the till and opens the books |
| SDKs | TypeScript (node:test) and Python (pytest) unit tests pass |
| Dependencies | `pip-audit` and `npm audit --omit=dev`: no known vulnerabilities |

## Bugs the pass found and fixed

- **Isolation sweep:** stock movements and webhook deliveries for another workspace's
  item answered an empty `200` instead of `404` (no data leaked: row-level security hid
  it). Both now check the parent first.
- **Remove sample data** crashed if a sample row was still referenced (it rolled back the
  whole request); now it keeps just that row.
- **Stock sold before its delivery was recorded** could give a negative average cost.
  The units sold early are now re-costed at the delivery's cost, posted as a separate
  "cost correction" (stock against cost of goods), so the books still balance
  (`costing.receive`, migration 0029). Found by the Hypothesis property test.
- **Workload signal** could never fire in a team of four (a mean + 2σ threshold); now it
  is "at least 8 open tasks and more than twice the team's typical load".
- **Low-stock alerts** skipped whoever made the sale, often the person who reorders.
- **A failed AI action** crashed while recording the failure (expired session rows after
  rollback).
- **SCIM** lived at `/scim/v2`, which the web origin doesn't forward to the API; moved to
  `/v1/scim/v2`.
- Tests that were wrong, not the code: event-log tests didn't expect `member.joined`;
  automation tests ran SQL without choosing the workspace (row-level security hid the
  rows); a workdays date; a till total that ignored "prices include VAT".

## Still not verified (needs real services or the owner)

- **Real providers:** Gemini with a real key; Google/Entra/Okta for company sign-in and
  SCIM; a real phone or security key for passkeys; real SMTP delivery; webhooks to a real
  HTTPS server (TLS SNI pinning).
- **Deployment:** Cloud Run, Neon, Cloudflare Pages, scheduled jobs, backups and a restore
  drill (`runbooks/deploy.md`, `runbooks/restore.md`); a ZAP scan and penetration test
  against that deployment.
- **Screens without their own browser journey** (they open cleanly and pass accessibility
  checks, and their APIs are tested): the automations editor, purchases/transfers/counts,
  hand journal entries and tax-return templates, webhook editor and delivery log, company
  sign-in settings, the network allowlist, the till PIN pad, passkey registration (needs
  a virtual authenticator), help search, the contact-support dialog.
- **Phone project** of the 19 older journeys wasn't re-run in this pass (desktop only).

## How to re-run everything

```bash
scripts/check.sh            # lint, types, import layers, migrations, API contract, API tests, web
E2E=1 scripts/check.sh      # plus the browser journeys (desktop and phone)
```

GitHub Actions (CI, CodeQL, Deploy) are switched off while the repository goes private
(owner, 2026-10-05). Re-enable them in Actions → each workflow → Enable workflow.
