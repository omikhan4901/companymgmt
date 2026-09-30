# Working on CompanyMgmt

Multi-tenant company management SaaS (HR, attendance, payroll, POS, inventory, accounting).
The plan is `docs/IMPLEMENTATION_PLAN.md`; progress and the next step are in
`docs/PROGRESS.md`. Read both before starting work, and update `PROGRESS.md` as you go.

## Conventions

- Commit as the owner, with no AI co-author lines and no model names:
  `git -c user.name=omikhan4901 -c user.email=mehboobehsankhan@gmail.com commit ...`
- Work on and push to `main` only. Small conventional commits (`feat:`, `fix:`, `test:`,
  `docs:`, `chore:`, `refactor:`).
- **Run `scripts/check.sh` before every push.** Push only when it passes. Never leave
  `main` broken. Gate the commit/push on the script's own exit code
  (`./scripts/check.sh > log; [ $? -eq 0 ] && git push`), never on a pipe into `grep`.
- Never `pkill -f`/`pgrep -f` a pattern that appears in your own command line (it kills the
  shell). Stop local servers with a small script file that matches by PID.
- Never commit secrets. Every variable goes in `.env.example` with no value.
- This session cannot push git tags.

## Layout

- `api/`: FastAPI modular monolith (Python 3.12, uv). Modules in `api/app/modules/<name>`,
  shared code in `api/app/core`. Alembic migrations in `api/migrations`.
- `web/`: React + TypeScript + Vite SPA (antd + Tailwind, ResumeX design language).
- `site/`: Astro marketing site (landing, pricing, legal).
- `infra/`: OpenTofu and deploy scripts. `docs/`: plan, progress, runbooks, security.

## Rules that are easy to break

- Every tenant table has `tenant_id`, forced RLS and a policy. The isolation tests fail
  otherwise. Global tables go on the allowlist in `api/tests/test_isolation_meta.py` with a
  reason.
- Money is integer minor units, never floats. Instants are `timestamptz` (UTC). The
  business date is computed in the branch timezone.
- Every route declares a permission (or explicitly opts out as public).
- Every state change that matters writes an audit event.
- User-facing strings go through i18n (English and Bangla).

## Working with the owner

- Look and feel: calm, uncluttered screens with little text. One clear next action;
  details only when needed. antd + Tailwind + motion, teal brand `#007B7B`. No dark
  gradient bands, glows or illustrated mock-ups (the owner reads them as "AI-looking").
  Dialogs never fill the screen.
- Tests are rigorous and edge-case heavy but fast.
- The owner isn't a cloud-console expert: give exact click paths or commands, and always
  the least-privilege option.
- Marketing and public pages only claim what is actually built.
- A routine (`trig_01BtkyYxPZW6r7FsBrpM5TLp`) wakes this session every 2 hours so work
  continues after usage-limit pauses. Disable it when only owner input is left.
