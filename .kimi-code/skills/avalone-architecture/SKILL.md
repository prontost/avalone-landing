# Avalone Architecture Skill

## Purpose

This skill defines the default engineering contract for the Avalone unified platform. All new code MUST be written in a class-based, dependency-injected, container/widget style inspired by FlutterFlow:

- Everything is a class or a method of a class.
- Business logic lives in services, not in routes or templates.
- UI is composed from reusable widgets/containers, never hardcoded inline.
- Dependencies are explicit and injected (constructor or FastAPI `Depends`).
- No magic strings, no hardcoded URLs, no direct SQL outside repositories.

## Default Rule: Classes First

When the user asks for any feature, bug fix, or refactor, the default implementation MUST use classes and DI. Do not write procedural helper functions unless you can prove a class is impossible or pointless.

If you encounter existing procedural/non-class code while working on a task:

1. Pause.
2. Ask the operator: "This file/module is currently procedural/functions-based. Should I refactor it to classes as part of this task, or keep the existing shape and only add the new class-based part?"
3. Do what the operator says.

Never silently leave new procedural code behind.

## Class Hierarchy & Subtypes

Model the domain as a hierarchy of thin, focused classes:

- **Entity / Model** — plain dataclasses or pydantic models (`User`, `Device`, `FeedbackMessage`).
- **Repository** — one per aggregate. Owns SQL/table name/queries. Returns models.
- **Service** — one per use-case or bounded context. Owns business rules. Depends on repositories and other services via constructor.
- **Widget / Container** — UI building blocks that render themselves from a context (`Shell`, `Card`, `AuthModal`, `ProfileSwitcher`).
- **Route Handler** — thin. Parses request, calls service, returns response/widget render.

When several things look similar, extract a base class or protocol:

```python
class Notifier(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...

class EmailNotifier(Notifier): ...
class SmsNotifier(Notifier): ...
```

Configure behavior through injected subtypes, not `if` chains.

## Containers, Not Pages

Avoid monolithic page templates with hardcoded markup. Instead:

- Build pages by composing container widgets.
- Each widget knows how to render itself from a typed context.
- Shared chrome (header, menu, modals) comes from `Shell` and friends in `avalone_core.ui`.

Example:

```python
page = Page(
    header=PageHeader(title=t("profile_title")),
    children=[
        IdentityCard(user=user),
        SecurityCard(user=user),
        SessionCard(),
    ],
)
```

## Dependency Injection Rules

1. Services receive dependencies in `__init__`.
2. FastAPI dependencies (`get_user_service`, `get_mail_service`, etc.) construct services with their dependencies.
3. Do not import global singletons inside business logic.
4. `settings()` is allowed only at composition/root level, never deep in services.

Good:

```python
class UserService:
    def __init__(self, repo: UserRepository, role_service: RoleService) -> None:
        self._repo = repo
        self._role_service = role_service
```

Bad:

```python
def update_user(user_id):
    con = sqlite3.connect(settings().db_path)  # hidden dependency
    ...
```

## No Hardcoding

- URLs: derive from `settings().web_base_url` or registry, never write `"https://avalone.online/profile"` in templates or Python.
- SQL table names: constants on the repository class.
- Strings: glossary keys; templates use `t(...)`.
- CSS class names: prefer semantic widget classes; avoid inline `style=` unless dynamic.
- Branch/app names: use `AvaloneRegistry`, never hardcode IDs.

## Repository Pattern

Every DB table has a repository class:

```python
class FeedbackRepository:
    TABLE = "avalone_feedback"

    def __init__(self, db: Database) -> None: ...
    def add(self, item: FeedbackMessage) -> FeedbackMessage: ...
    def list_recent(self, limit: int = 200) -> list[FeedbackMessage]: ...
```

No raw SQL in routes, services, or templates.

## When in Doubt

If a design choice forces you to write a hardcoded string, an `if settings().env == "..."` branch, or a procedural function, stop and ask the operator for the class-based way.

## Migration Strategy for Legacy Code

When asked to refactor broadly:

1. Inventory procedural modules.
2. Start from the outer leaves (routes/templates) and move inwards.
3. Introduce repositories first, then services, then widgets.
4. Keep behavior identical; do not change tests unless the test itself was testing implementation details.
5. Update this skill if the project evolves a new pattern.
