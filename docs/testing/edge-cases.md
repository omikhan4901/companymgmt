# Edge cases

From `IMPLEMENTATION_PLAN.md` §5.3. Each row names the test that covers it, or the
milestone where the feature arrives. Add a row for every bug found.

| # | Case | Covered by |
|---|---|---|
| 1 | Two managers edit the same record | `test_edit_person_with_concurrency`, `test_stale_member_edit_is_rejected`, `test_edit_and_delete_records_are_audited` (412) |
| 2 | Double click on an action | `test_double_click_clock_in_creates_one_record` (5 parallel clock-ins → 1) |
| 3 | Same idempotency key, different body | ⏳ M3 (idempotency keys arrive with sales) |
| 4 | Two cashiers sell the last unit | ⏳ M3 |
| 5 | Payroll finalized during an edit | ⏳ M2 |
| 6 | Two tabs refresh at once | `test_refresh_rotates_and_needs_client_header` (409 race, web client retries) |
| 7 | Events delivered twice or out of order | outbox handlers idempotent; billing ⏳ M6 |
| 8 | Leap years | `test_hours_across_daylight_saving_change` (29 Feb 2024); payroll ⏳ M2 |
| 9 | Joining or leaving mid-month | `test_edit_person_with_concurrency` (dates); proration ⏳ M2 |
| 10 | Overnight shift | `test_overnight_shift_belongs_to_the_day_it_started` |
| 11 | DST inside a shift | `test_hours_across_daylight_saving_change`, web `format.test.ts` |
| 12 | Branches in different zones | `test_overnight_shift_belongs_to_the_day_it_started` (local day wins), branch zone per record |
| 13 | Device clock skew | server stamps clock-in; `client_time` kept only for review |
| 14 | Clock-in at midnight | business date from the branch zone (10, 12) |
| 15 | Fiscal year July–June | BD default in `create_workspace`; `test_signup_creates_workspace_and_signs_in` |
| 16 | Token issued in the future | `decode_access_token` leeway 30 s, rejects beyond |
| 17 | Zero, negative, huge values | `test_manual_record_validation` (times); money ⏳ M2/M3 |
| 18 | Fractional quantities and rounding | ⏳ M3/M4 |
| 19 | Salary 0, deductions > gross | ⏳ M2 |
| 20 | Currencies with 0 or 3 decimals | ⏳ M2 |
| 21 | Discount ≥ price | ⏳ M3 |
| 22 | Names in Bangla, Arabic, emoji, 200 chars | `test_names_in_any_script`, `test_unicode_names_survive`, `test_csv_export_is_safe`, e2e staff in Bangla |
| 23 | Bangla digits typed in | web `normalizeDigits` + `format.test.ts` |
| 24 | Mixed LTR/RTL | `dir="auto"` on names in tables |
| 25 | Lookalike characters in usernames | usernames limited to `[a-z0-9._-]`; emails lower-cased |
| 26 | Same email, different case | `test_signup_rejects_duplicate_email_any_case`, `test_login_is_case_insensitive_and_returns_workspace` |
| 27 | Workspace deleted mid-request | 410 in `deps.py`; deletion flow ⏳ M2 |
| 28 | Plan changes mid-session | `test_trial_ends_on_free_plan`, `test_read_only_workspace_blocks_writes_not_reads` |
| 29 | Role changed while signed in | `test_role_change_applies_on_next_request` |
| 30 | Member removed while clocked in | `test_removing_a_member_closes_their_shift` |
| 31 | Last owner leaves | `test_last_owner_is_protected` |
| 32 | Invite expired, revoked or reused | `test_invites` |
| 33 | Module switched off with data | `test_modules_respect_requirements_and_plan` |
| 34 | Payroll fails half-way | ⏳ M2 |
| 35 | Email fails after commit | outbox retries with backoff (`core/outbox.py`) |
| 36 | Upload orphan | ⏳ M2 |
| 37 | Database cold start | `pool_pre_ping`; load test ⏳ |
| 38 | Export interrupted | ⏳ M2 |
| 39 | Malformed JSON, deep nesting | `test_malformed_and_oversized_payloads` |
| 40 | Oversized payloads | `test_malformed_and_oversized_payloads` (413) |
| 41 | Other workspace's ids, garbage ids | `test_api_never_crosses_workspaces`; FastAPI validates UUIDs (422) |
| 42 | Path traversal in file names | ⏳ M2 |
| 43 | Replayed refresh token | `test_refresh_token_reuse_revokes_session` |
| 44 | CSV with formulas | `test_csv_export_is_safe` |
| + | Forgot to clock out for a day | `test_forgot_to_clock_out_flow` |
| + | Overlapping shifts | `test_manual_record_validation` (database exclusion constraint) |
| + | Manager approves own request | `test_managers_cannot_approve_their_own_request` |
