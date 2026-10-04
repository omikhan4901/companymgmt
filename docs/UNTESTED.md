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
- [ ] **Writing help.** `POST /v1/ai/write` (draft, improve, shorter, translate) and
  `POST /v1/ai/documents/{id}/summary`; `app/ai/writing.py`; `documents.readable_text`;
  "Help me write" menu in the announcement and new-task dialogs; "Summarise" on documents.
  Writing and summaries now count towards the monthly allowance. Tests
  `test_writing_help_*` and `test_document_summaries_*` written, never run.
- [ ] **Automations (API).** New module `app/modules/automations` (schedule or event
  triggers, conditions, notify / create-task actions, recipients incl. overdue tasks and
  not clocked in), engine with rate limits, auto-pause, loop guard (`events.origin`),
  `member.joined` event, `/internal/automations/tick` (needs a Cloud Scheduler job every
  15 minutes, not added to infra yet), migration 0018, AI drafting
  `POST /v1/ai/automations/draft`. Tests in `api/tests/test_automations.py` and the
  isolation test, never run; migration applied locally only.
