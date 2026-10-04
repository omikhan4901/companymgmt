# Not yet tested

Since 2026-10-04 the owner asked for speed: code and unit tests are written, but only lint
and type checks are run locally. CI runs the tests on GitHub and may be red until a
test-and-fix pass. Everything below needs that pass: run `./scripts/check.sh` with
`E2E=1`, fix what breaks, then delete the entry.

Last fully green commit: `86be8ac` (M6 done, all API, web and browser tests passing).

## M7 AI actions and automation

- [ ] **Actions (propose → confirm).** New write capabilities `tasks.update`,
  `tasks.comment`, `leave.decide`, `announcements.post`; `ai_proposals` table (migration
  0017); `app/ai/actions.py`; confirm/cancel routes; action cards on the Ask page.
  Unit tests written in `api/tests/test_ai.py` (`test_actions_*`, `test_staff_cant_be_talked_*`)
  and the isolation test, never run. No browser test yet.
