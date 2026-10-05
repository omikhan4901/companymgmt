# Security policy

## Reporting a vulnerability

Email **security@companymgmt.app** with what you found, how to reproduce it, and what an
attacker could do with it. Please don't open a public issue, and don't access, change or
keep other people's data beyond what you need to show the problem.

- We reply within 3 working days and keep you posted until it's fixed.
- We aim to fix critical issues within 7 days and others within 30.
- We won't take legal action against good-faith research that follows this policy.
- We credit you in the changelog if you'd like.

Out of scope: denial of service, volume tests, social engineering, physical attacks,
findings that need a rooted device or an outdated browser, missing headers with no
demonstrated impact, and self-XSS.

## How CompanyMgmt is built to be safe

The details, with tests as evidence, are in [`docs/security/`](docs/security):

- **Tenant isolation in three layers:** every query is scoped by the app, Postgres
  row-level security is forced on every workspace table (the app's database role can't
  bypass it), and composite foreign keys stop cross-workspace references. An automatic
  test tries every id route with another workspace's ids.
- **Sign-in:** argon2id passwords checked against a breached-password list, two-step
  codes, passkeys, company sign-in (OpenID Connect), short-lived EdDSA access tokens kept
  in memory, rotating refresh tokens in a locked-down cookie (reuse ends the session),
  rate limits and a captcha after failures, emails on new-device sign-ins.
- **Every route declares who may call it**, checked by a test; permissions are enforced
  in one place for the app, the API and the AI assistant.
- **Encryption:** TLS everywhere, AES-256-GCM field encryption (with key ids for rotation)
  for national ids, two-step secrets, webhook and sign-in secrets.
- **Tamper-evident audit log:** a per-workspace hash chain, append-only for the app,
  exportable and verifiable.
- **Outbound requests** to addresses people type (webhooks, sign-in providers) only go
  to public HTTPS addresses, pinned to the checked IP.
- **AI:** the assistant can only use tools that check the person's own permissions;
  anything it proposes to change waits for the person to confirm. See
  [`docs/security/ai.md`](docs/security/ai.md).
- **Supply chain:** locked dependencies, weekly update PRs, audits with `pip-audit` and
  `npm audit`.
