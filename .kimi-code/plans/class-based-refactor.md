# Plan: Refactor Avalone to Class-Based DI Architecture

## Goal

Bring the entire Avalone codebase (landing + finance + shared core) in line with the `avalone-architecture` skill: everything is a class, dependencies are injected, UI is composed from widgets/containers, and nothing is hardcoded.

## Guiding Principles

1. **Classes by default** — no new procedural functions; existing ones become class methods or are replaced.
2. **Dependency injection** — services receive repositories and other services via `__init__`; routes receive services via FastAPI `Depends`.
3. **Repository per aggregate** — all SQL lives in repository classes; no raw SQL in services, routes, or templates.
4. **Widget/container UI** — pages are compositions of `Widget` subclasses; shared chrome comes from `Shell` and friends.
5. **No hardcoding** — URLs from registry/settings, strings from glossary, CSS classes semantic.
6. **Ask before preserving legacy** — when touching procedural code, ask whether to refactor it now or isolate it behind a class facade.

## Current State & Hotspots

### Repository / DB layer
- `avalone_core/db.py` — raw schema only; fine.
- `avalone_landing/core/user_repository.py` — already a repository; needs `name` column covered (done).
- `avalone_core/device_service.py`, `referral_service.py`, `language_service.py` — mix service logic with direct SQL; should split into repositories + services.
- `avalone_core/glossary_db.py` — migration + data; keep as-is but consider a `GlossaryRepository`.
- `avalone_landing/core/admin_service.py` — reads settings; okay, but could be split.
- `avalone_landing/core/mail_service.py` — already class-based; good.

### Service layer
- `AuthService` — class-based DI (good).
- `UserService` — class-based; depends on `UserRepository` (good).
- `RoleService` — class-based but uses direct DB in some methods; review.
- `DeviceService`, `ReferralService`, `LanguageService` — in `avalone_core`, act as both repo and service; split.
- `users.py` facade — legacy procedural wrapper; deprecate and migrate callers.

### Web / routes
- `avalone_landing/web/auth.py` — still has HTML form endpoints + new JSON modal endpoints; consolidate into a single `AuthController` class.
- `avalone_landing/web/admin_router.py` — procedural route code; should delegate to `AdminService` and widget classes.
- `avalone_landing/web/api/*.py` — mostly thin; misc.py still touches DB directly for feedback; create `FeedbackRepository`/`FeedbackService`.
- `avalone_landing/web/app.py` — `_render_shell` uses legacy `users` facade; switch to `UserService` + `AuthService`.

### UI / Templates
- `avalone_core/ui/templates/shell.html` — large; split into widget templates (`ProfileMenu`, `AppSwitcher`, `AuthModal`, etc.) instead of inline blocks.
- `avalone_landing/web/templates/*.html` — pages should compose widgets, not hardcode markup.
- `avalone_core/ui/widgets.py` — add more widgets: `ProfileSwitcher`, `AuthModal`, `Page`, `FormCard`, etc.

### Finance module
- `avalone_finance/core/external_auth.py` — reads cookie directly; create shared `AuthService` interface or reuse landing `AuthService`.
- Several finance services likely procedural; audit and refactor after landing core is clean.

## Phases

### Phase 1: Shared Core Repositories
1. Create `avalone_core/repositories/` package.
2. Move SQL from `DeviceService` → `DeviceRepository`.
3. Move SQL from `ReferralService` → `ReferralRepository`.
4. Move SQL from `LanguageService` → `LanguageRepository`.
5. Keep service classes but inject repositories.
6. Update all callers.

### Phase 2: Landing Services & DI
1. Ensure `UserService`, `AuthService`, `RoleService`, `MailService` receive dependencies in constructors.
2. Create `FeedbackService` + `FeedbackRepository`; remove raw SQL from `misc.py`.
3. Replace `avalone_landing.core.users` facade usage with injected `UserService`/`AuthService`.

### Phase 3: Auth Controller
1. Create `AuthController` class (or `AuthService` methods) handling login/register/forgot/reset.
2. Merge existing HTML and JSON routes into a single clean set; pages become thin wrappers around the modal.
3. Remove duplicate validation logic.

### Phase 4: UI Widgets
1. Refactor `shell.html` into smaller widget templates (`ProfileMenu`, `AppSwitcher`, `AuthModal`, `FeedbackModal`, `SearchOverlay`).
2. Refactor page templates (`profile.html`, `landing.html`, admin pages) to compose widgets.
3. Introduce `Page`, `Card`, `FormCard`, `ButtonGroup` widgets.

### Phase 5: Admin & Misc Routes
1. Convert `admin_router.py` to use widgets and services.
2. Create `AdminController`/`AdminService` for user/role/settings operations.
3. Remove direct DB access from admin routes.

### Phase 6: Finance Alignment
1. Reuse shared `AuthService` for SSO.
2. Apply same repository/service split to finance modules.

### Phase 7: Tests & Cleanup
1. Update tests to construct services with fakes/mocks where useful.
2. Remove dead templates, routes, and procedural helpers.
3. Run full test suite; add tests for new classes.

## Order of Attack (Recommended)

1. Start with `FeedbackRepository`/`FeedbackService` — small, isolated, good proof of concept.
2. Refactor `DeviceService` + `DeviceRepository` — touches screen-time and heartbeat.
3. Refactor `ReferralService` + `ReferralRepository`.
4. Refactor `LanguageService` + `LanguageRepository`.
5. Replace `users.py` facade in `app.py` and admin routes.
6. Consolidate auth routes into `AuthController`.
7. Refactor shell into widgets.
8. Refactor admin routes.
9. Audit finance module.

## Definition of Done

- No raw SQL outside repositories.
- No procedural business logic outside classes.
- No hardcoded URLs/strings in templates or Python (except config).
- All services injected.
- All pages composed from widgets.
- Full test suite passes.

## Notes

- This plan is intentionally broad. Before each phase, confirm scope with the operator.
- The `avalone-architecture` skill should be updated if new patterns emerge during implementation.
