# Working on CompanyMgmt

Multi-tenant company management SaaS (HR, attendance, payroll, POS, inventory, accounting).
The plan is `docs/IMPLEMENTATION_PLAN.md`; progress and the next step are in
`docs/PROGRESS.md`. Read both before starting work, and update `PROGRESS.md` as you go.
`docs/GUIDE.md` explains how everything works (keep it true when you change how things work).

## Conventions

- Commit as the owner, with no AI co-author lines and no model names:
  `git -c user.name=omikhan4901 -c user.email=mehboobehsankhan@gmail.com commit ...`
- Work on and push to `main` only. Small conventional commits (`feat:`, `fix:`, `test:`,
  `docs:`, `chore:`, `refactor:`).
- Speed mode (2026-10-04) ended with the test-and-fix pass on 2026-10-05
  (`docs/UNTESTED.md` records what ran and what still needs real services). GitHub
  Actions are switched off while the repository goes private (owner), so
  `scripts/check.sh` locally is the only gate.
- **Run `scripts/check.sh` before every push.** Push only when it passes. Never leave
  `main` broken. Gate the commit/push on the script's own exit code
  (`./scripts/check.sh > log; [ $? -eq 0 ] && git push`), never on a pipe into `grep`.
- **After a container restart**: set the repo git identity again (`omikhan4901`,
  `mehboobehsankhan@gmail.com`), start Postgres (`service postgresql start`), and if
  Playwright can't find its browser run e2e with `PW_CHROMIUM_PATH=/opt/pw-browsers/chromium`.
- Never `pkill -f`/`pgrep -f` a pattern that appears in your own command line (it kills the
  shell). Stop local servers with a small script file that matches by PID.
- Never commit secrets. Every variable goes in `.env.example` with no value.
- This session cannot push git tags.

## Layout

- `api/`: FastAPI modular monolith (Python 3.12, uv). Modules in `api/app/modules/<name>`,
  shared code in `api/app/core`. Alembic migrations in `api/migrations`.
- `web/`: one Next.js app (App Router, TypeScript, static export) for the marketing site
  (`src/app/(site)`) and the product (`src/app/(product)`: sign-in pages and `/app/*`).
  Atlas design (docs/design/atlas): tokens in `src/app/globals.css`, light by default,
  dark and four accents via `src/lib/theme.tsx`. Components in `src/components/ui`
  (Radix + Tailwind). `npm run build` also writes `out/_headers` with a per-page CSP;
  `npm run serve` serves `out/` like Cloudflare and proxies `/v1` to the API.
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
  details only when needed. Atlas design (docs/design/atlas): white by default, dark
  mode, accents Plum (default) / Saffron / Garnet / Ink; never blue or neon. Radix +
  Tailwind, no antd. No gradient washes, glows or illustrated mock-ups (the owner reads
  them as "AI-looking"). Dialogs never fill the screen on desktop; phones get sheets.
- Attendance is location-based: new attendance features must respect the workspace's
  location mode and never track people between clock events.
- Design new modules AI-ready (plan §3.7): logic in typed service functions, not routes.
- Tests are rigorous and edge-case heavy but fast.
- The owner isn't a cloud-console expert: give exact click paths or commands, and always
  the least-privilege option.
- Marketing and public pages only claim what is actually built.
- No inline scripts or `dangerouslySetInnerHTML`: the CSP allows only each page's own
  Next.js scripts by hash. Anything that must run before paint goes in `public/*.js`.
- Every UI string exists in `web/src/i18n/en.ts` and `bn.ts` (TypeScript checks this).
- A routine (`trig_01BtkyYxPZW6r7FsBrpM5TLp`) wakes this session every 2 hours so work
  continues after usage-limit pauses. Follow "Owner decisions, 2026-10-04" in
  `docs/PROGRESS.md` for the order and scope. Disable it when only owner input is left.
- The public marketing site uses the ResumeX look (teal, Inter / Plus Jakarta Sans); the
  product under `/app` uses Atlas. Don't mix them.
