# The CompanyMgmt handbook

Everything you need to run, understand, change and operate CompanyMgmt by yourself. It
assumes you can use a terminal and have written a little code; it doesn't assume you
know FastAPI, SQLAlchemy, Next.js or Postgres row-level security. Each chapter explains the
idea first, then points at the exact files, and links a good tutorial when a new tool comes
up.

## Chapters

| # | Chapter | Read it when you want to… |
|---|---|---|
| 1 | [The product](01-the-product.md) | know what it does, for whom, the modules, plans and roles |
| 2 | [Run it on your computer](02-run-locally.md) | turn it on: install, database, settings, demo data, troubleshooting |
| 3 | [Architecture](03-architecture.md) | see how a request travels, how tenants are kept apart, events, jobs, AI |
| 4 | [The backend, file by file](04-backend.md) | read and change the Python API |
| 5 | [Every module](05-modules.md) | know what each feature area stores, its rules, routes, events and permissions |
| 6 | [The frontend](06-frontend.md) | read and change the Next.js site and app |
| 7 | [User flows](07-user-flows.md) | follow what happens, screen by screen and call by call, for each journey |
| 8 | [Security](08-security.md) | understand every protection and what you must never break |
| 9 | [Testing](09-testing.md) | run, read and write API, unit and browser tests |
| 10 | [Production at the lowest cost](10-production.md) | go live for about $1 a month and know what grows the bill |
| 11 | [Operating it](11-operations.md) | deploy updates, watch it, back up and restore, rotate keys, handle incidents |
| 12 | [Adding a feature](12-extending.md) | build something new end to end, with a worked example |
| 13 | [Reference](13-reference.md) | look up settings, scripts, permissions, events, error codes, jobs, glossary |

## Reading order

- **First day:** chapters 1 and 2. Get it running, sign up, click around, load the demo data.
- **First week:** chapters 3, 4 and 6, with the code open next to them. Then chapter 12's
  worked example, typed out yourself.
- **Before going live:** chapters 8, 10 and 11.
- **Whenever:** 5, 7, 9 and 13 are reference; dip in when you work on an area.

## Other documents in the repository

| Document | What it is |
|---|---|
| [`README.md`](../../README.md) | The front page: what it does, screenshots, status |
| [`CLAUDE.md`](../../CLAUDE.md) | The house rules for anyone (person or AI) changing the code |
| [`docs/IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md) | The original plan: audit of the university project, product scope, architecture decisions, costs, roadmap |
| [`docs/PROGRESS.md`](../PROGRESS.md) | What was built when, the owner's decisions, what's blocked on you |
| [`docs/UNTESTED.md`](../UNTESTED.md) | Test status: what ran, the bugs found, what still needs real services |
| [`docs/api/README.md`](../api/README.md) | The public API guide for customers' developers (keys, webhooks, SSO, SCIM) |
| [`docs/runbooks/`](../runbooks/) | Step-by-step operations: deploy, restore, incident |
| [`docs/security/`](../security/) | ASVS level 2 checklist with evidence, AI threat model |
| [`docs/legal/REVIEW.md`](../legal/REVIEW.md) | The legal review: gaps found, fixes, questions for a lawyer |
| [`docs/pilot-playbook.md`](../pilot-playbook.md) | How to run the first pilot companies |
| [`sdk/README.md`](../../sdk/README.md) | The TypeScript and Python SDKs |

`docs/GUIDE.md`, the earlier developer guide, now points here.

## Conventions in this handbook

- Paths are from the repository root: `api/app/core/db.py`.
- `$` lines are shell commands; run them from the repository root unless a `cd` says otherwise.
- "Workspace" and "tenant" mean the same thing: one company and all its data.
- Money is always in minor units (paisa, cents): `150000` is ৳1,500.00.
- Numbers like test counts are as of 5 October 2026; `scripts/check.sh` prints today's.
