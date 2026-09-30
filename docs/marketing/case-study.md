# Case study: from a class project to a multi-tenant SaaS

**Mehboob Ehsan Khan** · 2026 · [github.com/omikhan4901/companymgmt](https://github.com/omikhan4901/companymgmt)

## The problem

Our CSE327 group project at North South University was a company management system
built to show design patterns: a single FastAPI file of 1,000 lines, SQLite, and sessions
in memory. Reviewing it as a product found unsalted SHA-256 passwords, a default
`admin/admin` account, money stored as floats, dates stored as strings, and no concept of
separate companies. It couldn't serve even one real business safely.

## The goal

A product any business can sign up for and use without help: a tea stall with two staff
or a company with branches. It had to work in Bangla on cheap phones, meet OWASP ASVS
Level 2, and cost nothing to run until there are customers.

## What I did

- **Wrote the plan first.** Audited the old code file by file, chose a stack by cost and
  fit, mapped security requirements to ASVS 5.0, and split the product into milestones that
  each ship complete ([implementation plan](../IMPLEMENTATION_PLAN.md)).
- **Made tenant isolation the database's job.** Every tenant table uses forced Postgres
  row-level security. The API's database role can't bypass it, and composite foreign keys
  stop cross-company references. A test discovers every API route that takes an ID and
  calls it with another company's IDs.
- **Built authentication properly.** Argon2id passwords checked against a list of 100,000
  breached passwords. Short-lived EdDSA access tokens. Rotating refresh tokens, where
  reusing an old one ends the session. TOTP two-step verification, step-up confirmation,
  and rate limits with a CAPTCHA fallback.
- **Designed for real workplaces.** Staff accounts without email. Overnight shifts that
  count towards the right day. A time zone per branch. Correction requests with approval,
  where you can't approve your own. A tamper-evident audit log.
- **Kept costs at zero while idle.** Cloud Run, Neon serverless Postgres and Cloudflare
  Pages all scale to zero. Infrastructure is code (OpenTofu), and deploys use GitHub OIDC
  instead of stored keys.

## Results (Milestone 1)

- 105 API tests at 90% line and branch coverage, all against real Postgres.
- Browser journeys on desktop and phone, in English and Bangla, with WCAG 2.2 AA checks on
  every page. They caught real contrast, touch-target and keyboard-scrolling issues, which
  are now fixed.
- CI runs linting, strict typing, a migration drift check, an API contract check, secret
  scanning, dependency audits, a container scan and CodeQL on every push.

## What I learned

- Putting the security rule in the database (RLS) made isolation testable by default,
  instead of hoping every query remembered a filter.
- Automated accessibility checks find real problems that are easy to miss by eye.
- Writing down what *isn't* built yet keeps the marketing honest.

## Next

Payroll with a Bangladesh preset, a point of sale with customer dues, then inventory and
double-entry accounting.
