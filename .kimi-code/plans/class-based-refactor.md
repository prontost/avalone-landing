# Plan: Refactor Avalone to Class-Based DI Architecture

## Goal

Bring the entire Avalone codebase (landing + finance + shared core) in line with the global `class-first-architecture` and `standard-ux-patterns` skills:

- Everything is a class.
- Dependencies are injected.
- UI is composed from widgets/containers.
- Well-known UX patterns are used by default.
- Nothing is hardcoded.

## Guiding Principles

1. **Classes by default** — no new procedural functions; existing ones become class methods or are replaced.
2. **Dependency injection** — services receive repositories and other services via `__init__`; routes receive services via FastAPI `Depends`.
3. **Repository per aggregate** — all SQL lives in repository classes; no raw SQL in services, routes, or templates.
4. **Service layer** — business rules live in small, focused services that depend on repositories and other services.
5. **Widget/container UI** — pages are compositions of `Widget` subclasses; shared chrome comes from `Shell` and friends.
6. **Standard UX patterns first** — reuse patterns users already know (Google account switcher, modal auth, settings forms, etc.); only invent custom flows when no standard fits.
7. **No hardcoding** — URLs from registry/settings, strings from glossary, CSS classes semantic, feature flags from settings/DB.
8. **Ask before preserving legacy** — when touching procedural code, ask whether to refactor it now or isolate it behind a class facade.

## Account Management Domain

Authentication and account management must be a single coherent subsystem, not scattered routes:

- **Account lifecycle** — sign up, sign in, sign out, switch account, add account, remove account session.
- **Password security** — change password, reset password via email token, enforce policy, invalidate other sessions on password change.
- **Email identity** — add email, verify email, replace email, require verified email for sensitive actions.
- **Profile** — display name, avatar/initials, contact info, language, theme.
- **Session management** — list active sessions, revoke individual sessions, revoke all except current.
- **Roles & permissions** — owner/admin/user roles, permission checks in services, not routes.

All of the above should be implemented through:

- `AccountService` / `AuthService` / `UserService` / `RoleService` / `SessionService`.
- `UserRepository` / `SessionRepository` / `EmailVerificationRepository`.
- `AuthModal`, `AccountSwitcher`, `ProfileCard`, `SecurityCard`, `SessionList` widgets.

## Current State & Hotspots

### Repository / DB layer
- `avalone_core/db.py` — raw schema only; fine.
- `avalone_landing/core/user_repository.py` — already a repository; `name` column covered.
- `avalone_core/device_service.py`, `referral_service.py`, `language_service.py` — mix service logic with direct SQL; split into repositories + services.
- `avalone_core/glossary_db.py` — migration + data; wrap access in `GlossaryRepository`/`LanguageService`.
- `avalone_landing/core/admin_service.py` — reads settings; okay, but could be split into `SettingsRepository` + `AdminService`.
- `avalone_landing/core/mail_service.py` — already class-based; good.
- Missing: `FeedbackRepository`, `SessionRepository`, `SettingsRepository`, `EmailVerificationRepository`.

### Service layer
- `AuthService` — class-based DI (good).
- `UserService` — class-based; depends on `UserRepository` (good).
- `RoleService` — class-based but uses direct DB in some methods; review and inject repository.
- `DeviceService`, `ReferralService`, `LanguageService` — in `avalone_core`, act as both repo and service; split.
- `users.py` facade — legacy procedural wrapper; deprecate and migrate callers to injected services.

### Web / routes
- `avalone_landing/web/auth.py` — still has HTML form endpoints + JSON modal endpoints; consolidate into a single `AuthController` class.
- `avalone_landing/web/admin_router.py` — procedural route code; should delegate to `AdminService` and widget classes.
- `avalone_landing/web/api/*.py` — mostly thin; `misc.py` still touches DB directly for feedback; create `FeedbackService`.
- `avalone_landing/web/app.py` — `_render_shell` uses legacy `users` facade; switch to `UserService` + `AuthService`.

### UI / Templates
- `avalone_core/ui/templates/shell.html` — large; split into widget templates (`ProfileMenu`, `AppSwitcher`, `AuthModal`, `FeedbackModal`, `SearchOverlay`, `AccountSwitcher`).
- `avalone_landing/web/templates/*.html` — pages should compose widgets, not hardcode markup.
- `avalone_core/ui/widgets.py` — add more widgets: `ProfileSwitcher`, `AuthModal`, `Page`, `FormCard`, `ButtonGroup`, `EmptyState`, `DataTable`.

### Configuration & Registry
- `AvaloneRegistry` is good for app branches; extend usage so no app IDs are hardcoded.
- `settings()` should be read at composition/root level, not deep in services.
- Global server settings (registration mode, mail config, etc.) should have a `SettingsRepository` with DB override.

### Finance module
- `avalone_finance/core/external_auth.py` — reads cookie directly; reuse shared `AuthService`.
- Several finance services likely procedural; audit and refactor after landing core is clean.

## Phases

### Phase 0: Foundations
1. Create `avalone_core/repositories/` package.
2. Define base `Repository` class with shared DB access patterns.
3. Create `SettingsRepository` for runtime DB overrides.
4. Update `class-first-architecture` skill if new conventions emerge.

### Phase 1: Shared Core Repositories
1. `FeedbackRepository` + `FeedbackService`.
2. `DeviceRepository` + `DeviceService`.
3. `ReferralRepository` + `ReferralService`.
4. `LanguageRepository` + `LanguageService`.
5. `GlossaryRepository` for read access to translations.
6. Keep service classes but inject repositories.
7. Update all callers.

### Phase 2: Account & Session Subsystem
1. Add `SessionRepository` for multi-session cookie + server-side session metadata.
2. Create `AccountService` that coordinates `UserService`, `AuthService`, `MailService`, `RoleService`.
3. Implement session list/revoke features.
4. Unify password reset, change, and verification flows under services.
5. Replace `users.py` facade usage with injected services.

### Phase 3: Auth Controller & Modal
1. Create `AuthController` class handling login/register/forgot/reset/session operations.
2. Merge HTML and JSON routes into a clean API used by the `AuthModal` widget.
3. Remove duplicate validation logic.
4. Ensure fallback pages still render correctly.

### Phase 4: UI Widgets
1. Refactor `shell.html` into smaller widget templates.
2. Extract `AccountSwitcher`, `ProfileMenu`, `AuthModal`, `FeedbackModal`, `SearchOverlay`.
3. Refactor page templates (`profile.html`, `landing.html`, admin pages) to compose widgets.
4. Introduce `Page`, `Card`, `FormCard`, `ButtonGroup`, `EmptyState`, `DataTable` widgets.
5. Apply standard UX patterns from `standard-ux-patterns` skill.

### Phase 5: Admin & Settings
1. Convert `admin_router.py` to use widgets and services.
2. Create `AdminController`/`AdminService` for users, roles, feedback, settings.
3. Remove direct DB access from admin routes.
4. Build reusable admin widgets (`UserTable`, `RoleEditor`, `SettingsForm`).

### Phase 6: Finance Alignment
1. Reuse shared `AuthService` for SSO.
2. Apply repository/service split to finance modules.
3. Align finance UI widgets with landing widgets.

### Phase 7: Tests & Cleanup
1. Update tests to construct services with fakes/mocks where useful.
2. Add unit tests for repositories and services.
3. Add integration tests for auth/account flows.
4. Remove dead templates, routes, and procedural helpers.
5. Run full test suite.

## Order of Attack (Recommended)

1. `SettingsRepository` + runtime settings cleanup.
2. `FeedbackRepository`/`FeedbackService` — small, isolated proof of concept.
3. `DeviceRepository`/`DeviceService`.
4. `ReferralRepository`/`ReferralService`.
5. `LanguageRepository`/`LanguageService` + `GlossaryRepository`.
6. `SessionRepository` + multi-session improvements.
7. `AccountService` and unification of auth/account flows.
8. Replace `users.py` facade.
9. `AuthController` + modal consolidation.
10. Shell widget decomposition.
11. Page widget composition.
12. Admin refactor.
13. Finance audit.
14. Test cleanup.

## Definition of Done

- No raw SQL outside repositories.
- No procedural business logic outside classes.
- No hardcoded URLs/strings in templates or Python (except config).
- All services receive dependencies via constructor.
- All pages composed from widgets.
- Auth/account flows follow standard UX patterns.
- Full test suite passes.

## Notes

- This plan is intentionally broad. Before each phase, confirm scope with the operator.
- Update the `class-first-architecture` and `standard-ux-patterns` skills if new patterns emerge.
- Prefer small, reviewable PRs/commits per phase rather than one giant refactor.
