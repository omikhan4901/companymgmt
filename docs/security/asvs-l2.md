# OWASP ASVS 5.0 Level 2: status and evidence

This tracks the security requirements in `IMPLEMENTATION_PLAN.md` §4 (mapped to ASVS 5.0
chapters). **Status**: ✅ done with evidence · 🟡 partly done · ⏳ planned (milestone).
Evidence names tests in `api/tests` (API), `web/e2e` (browser) or files.

The next step (M1 hardening) is a line-by-line pass over every ASVS 5.0 L1+L2 requirement
ID from the official text, added as a second table here.

## V8 Authorization and tenant isolation

| # | Requirement | Status | Evidence |
|---|---|---|---|
| S1 | Forced RLS and a policy on every tenant table | ✅ | `test_isolation.py::test_every_tenant_table_is_protected` |
| S2 | App role has no BYPASSRLS, isn't owner or superuser | ✅ | `test_app_role_cannot_bypass_rls` |
| S3 | No tenant bound → no rows, no writes | ✅ | `test_database_level_isolation` |
| S4 | Every id route rejects another workspace's ids (auto-discovered) | ✅ | `test_api_never_crosses_workspaces` |
| S5 | Raw SQL as the app role can't read or move other tenants' rows | ✅ | `test_database_level_isolation` |
| S6 | Composite foreign keys stop cross-tenant references | ✅ | models (`ForeignKeyConstraint` on `(tenant_id, id)`), `test_database_level_isolation` |
| S7 | Presigned file URLs after authorization | ⏳ M2 | no file uploads yet |
| S8 | Jobs refuse to run without tenant context | 🟡 | session context fails closed (`current_tenant`); job framework in M2 |
| R1 | Every route declares its access | ✅ | `test_platform.py::test_every_route_declares_who_may_call_it`, `test_public_routes_are_the_expected_few` |
| R2 | Built-in roles, least privilege by default | ✅ | `catalog.py`, `test_permissions_referenced_by_roles_exist` |
| R3 | Department scope for managers | ✅ | `test_manager_sees_only_their_department`, `test_scope_limits_what_managers_see` |
| R4 | Custom roles can't exceed the creator's permissions | ✅ | `test_admins_cannot_escalate`, `test_custom_roles` |
| R5 | Role changes apply on the next request | ✅ | `test_role_change_applies_on_next_request` |
| R6 | Object-level checks | ✅ | people/attendance scope tests, isolation sweep |
| R7 | Last owner protected | ✅ | `test_last_owner_is_protected` |

## V6 Authentication · V7 Sessions · V9 Tokens

| # | Requirement | Status | Evidence |
|---|---|---|---|
| A1 | argon2id hashing, rehash on parameter change | ✅ | `security/passwords.py`, `test_password_hashing` |
| A2 | Min 8, max 128, Unicode, breached-list check, no context words | ✅ | `test_signup_password_rules` (NCSC 100k list bundled) |
| A3 | Email verification before invites | ✅ | `test_invites` (email_unverified) |
| A4 | EdDSA access tokens, 10 min, pinned algorithm, memory only | ✅ | `test_forged_and_expired_tokens_are_rejected`, `web/src/api/client.ts` |
| A5 | Rotating refresh token, hashed, httpOnly/Secure/Strict cookie, reuse revokes session | ✅ | `test_refresh_cookie_is_locked_down`, `test_refresh_rotates_and_needs_client_header`, `test_refresh_token_reuse_revokes_session` |
| A6 | Session list and revocation, checked every request | ✅ | `test_sessions_list_and_revoke`, `test_logout_ends_session` |
| A7 | TOTP with recovery codes, secret encrypted | ✅ | `test_mfa_enable_and_login`, `test_mfa_recovery_code_is_single_use` |
| A7b | Workspace policy to require MFA for admins | ⏳ M2 | |
| A8 | Step-up before sensitive actions | 🟡 | MFA changes (`test_sensitive_actions_need_recent_sign_in`); payroll/export in M2 |
| A9 | Rate limits, captcha after failures, generic errors | ✅ | `test_login_rate_limit_per_account`, `test_captcha_required_after_failures`, `test_login_failures_look_the_same` |
| A10 | Reset tokens: single use, 30 min, sessions revoked | ✅ | `test_password_reset_flow` |
| A11 | POS device PIN | ⏳ M3 | |
| A12 | Auth events recorded | ✅ | `auth_events` table (append-only) |

## V16 Logging

| # | Requirement | Status | Evidence |
|---|---|---|---|
| L1 | Audit log append-only for the app | ✅ | `test_audit_log_is_append_only_for_the_app` |
| L2 | Per-tenant hash chain, verification | ✅ | `test_audit_log_records_and_verifies` (detects a direct DB edit) |
| L2b | Daily chain-head anchor to R2 | ⏳ | |
| L3 | Who/what/when/where on each event | ✅ | `core/audit.py` |
| L4 | No secrets in logs | ✅ | `redact()`, `test_audit_hash_changes_with_any_field`, `test_national_id_is_encrypted_and_masked` |
| L5 | View/filter/verify in the app; retention by plan | 🟡 | view/filter/verify ✅; retention purge job ⏳ |

## V11–V14 Crypto, transport, configuration, data protection

| # | Requirement | Status | Evidence |
|---|---|---|---|
| D1 | TLS everywhere, HSTS | ✅ | HSTS in prod (verified on the image), `sslmode=verify-full` in the runbook |
| D2 | Field encryption (AES-256-GCM, bound context, key ids) | ✅ | `test_field_encryption_is_bound_to_its_context`, `test_national_id_is_encrypted_and_masked` |
| D3 | Secrets in Secret Manager, OIDC deploys, no keys | ✅ | `infra/gcp`, `deploy.yml`, prod refuses to start without secrets |
| D4 | Security headers, strict CSP | ✅ | `test_security_headers`; SPA/site `_headers` |
| D5 | Validation, unknown fields rejected, size limits | ✅ | `test_signup_rejects_unknown_fields_and_bad_timezone`, `test_malformed_and_oversized_payloads` |
| D6 | No string-built SQL | ✅ | ORM/bound params only; the few `text()` queries use parameters |
| D7 | XSS: no raw HTML | ✅ | ESLint rule bans `dangerouslySetInnerHTML` |
| D8 | CSRF on the cookie endpoint | ✅ | `test_refresh_rotates_and_needs_client_header` (header + Origin), CORS test |
| D9 | SSRF guard | ⏳ M7 | no user-supplied URLs are fetched |
| D10 | File upload checks | ⏳ M2 | |
| D11 | CSV formula injection | ✅ | `test_csv_export_is_safe` |
| D12 | No internals in errors; docs off in prod | ✅ | error handlers; `/docs` 404 in prod (verified) |

## V15 Supply chain

| # | Requirement | Status | Evidence |
|---|---|---|---|
| C1 | Locked dependencies, weekly updates | ✅ | `uv.lock`, `package-lock.json`, `.github/dependabot.yml` |
| C2 | pip-audit, npm audit, gitleaks, CodeQL, Trivy in CI | ✅ | `.github/workflows/ci.yml`, `codeql.yml` |
| C3 | Branch protection with required checks | ⏳ owner | GitHub → Settings → Branches (runbook) |
| C4 | Non-root, slim image | ✅ | uid 10001 (verified) |

## V14 Privacy, export, deletion, backups

| # | Requirement | Status |
|---|---|---|
| P1 | Workspace export | 🟡 attendance CSV ✅; full export ⏳ M2 |
| P2 | Personal data export | ⏳ M2 |
| P3 | Workspace deletion with grace period | ⏳ M2 |
| P4 | Member removal keeps legal records | ✅ removed members keep history; access revoked |
| P5 | Backups | 🟡 Neon PITR ✅; nightly dump ⏳ |
| P6 | Restore runbook and drill | 🟡 `docs/runbooks/restore.md`; first drill after deploy |
| P7 | Privacy policy and terms | 🟡 drafts published; legal review pending (owner) |
