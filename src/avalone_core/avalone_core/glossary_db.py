"""Unified DB-backed glossary for the whole Avalone platform.

Design goals:
- One table `avalone_glossary` is the single source of truth.
- Every user-facing phrase is keyed; languages are translations, not the source.
- Every key has a `desc` (meta-context) so AI/human translators know role and location.
- Backwards-compatible API for the old `counta.core.glossary` / `routa.core.glossary` modules.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from avalone_core.db import connection

LANGS = ("ru", "en", "ko")

SCHEMA = """
CREATE TABLE IF NOT EXISTS avalone_glossary (
    key        TEXT PRIMARY KEY,
    ru         TEXT,
    en         TEXT,
    ko         TEXT,
    kind       TEXT DEFAULT 'ui',
    module     TEXT DEFAULT '',
    desc       TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_avalone_glossary_kind   ON avalone_glossary(kind);
CREATE INDEX IF NOT EXISTS idx_avalone_glossary_module ON avalone_glossary(module);
"""

# Seed data for the portal / shared shell. Domain keys (Counta/Routa categories,
# currencies, etc.) are migrated from legacy tables or seeded by the apps.
_PORTAL_SEED: list[dict[str, Any]] = [
    # Apps
    {"key": "app_work",       "ru": "Работа",     "en": "Work",      "ko": "업무",      "kind": "ui", "module": "portal"},
    {"key": "app_money",      "ru": "Финансы",    "en": "Finance",   "ko": "재정",      "kind": "ui", "module": "portal"},
    {"key": "app_education",  "ru": "Обучение",   "en": "Education", "ko": "교육",      "kind": "ui", "module": "portal"},
    {"key": "app_living",     "ru": "Жильё",      "en": "Living",    "ko": "주거",      "kind": "ui", "module": "portal"},
    {"key": "app_travel",     "ru": "Поездки",    "en": "Travel",    "ko": "여행",      "kind": "ui", "module": "portal"},
    {"key": "app_health",     "ru": "Здоровье",   "en": "Health",    "ko": "건강",      "kind": "ui", "module": "portal"},

    # App descriptions
    {"key": "app_work_desc",      "ru": "Арбайт, смены, поездки, фриланс, карьера.",                       "en": "Part-time, shifts, rides, freelance, career.",            "ko": "아륰바이트, 교대, 출퇴근, 프리랜스, 경력.",              "kind": "ui", "module": "portal"},
    {"key": "app_money_desc",     "ru": "Учёт, бюджет, аналитика, советы.",                                "en": "Tracking, budget, analytics, tips.",                        "ko": "가계부, 예산, 분석, 팁.",                                "kind": "ui", "module": "portal"},
    {"key": "app_education_desc", "ru": "Курсы, языки, переподготовка, адаптация.",                        "en": "Courses, languages, retraining, adaptation.",               "ko": "강좌, 언어, 재교육, 적응.",                              "kind": "ui", "module": "portal"},
    {"key": "app_living_desc",    "ru": "Аренда, соседи, бытовые вопросы.",                                "en": "Rent, neighbors, household issues.",                        "ko": "임대, 이웃, 가사 문제.",                                "kind": "ui", "module": "portal"},
    {"key": "app_travel_desc",    "ru": "Трансферы, экскурсии, путешествия.",                              "en": "Transfers, excursions, travel.",                            "ko": "이동, 투어, 여행.",                                      "kind": "ui", "module": "portal"},
    {"key": "app_health_desc",    "ru": "Клиники, страховка, записи.",                                     "en": "Clinics, insurance, appointments.",                         "ko": "병원, 보험, 예약.",                                      "kind": "ui", "module": "portal"},

    # Statuses
    {"key": "status_active",  "ru": "Работает",      "en": "Live",           "ko": "실행 중",    "kind": "ui", "module": "portal"},
    {"key": "status_planned", "ru": "В планах",      "en": "Planned",        "ko": "계획 중",    "kind": "ui", "module": "portal"},
    {"key": "status_in_dev",  "ru": "В разработке",  "en": "In development", "ko": "개발 중",    "kind": "ui", "module": "portal"},

    # Common
    {"key": "brand",          "ru": "Avalone",    "en": "Avalone",   "ko": "Avalone",   "kind": "ui", "module": "portal"},
    {"key": "brand_tagline",  "ru": "Ваши инструменты в одном месте", "en": "Your tools in one place", "ko": "모든 도구가 한 곳에", "kind": "ui", "module": "portal"},
    {"key": "portal_title",   "ru": "Портал",     "en": "Portal",    "ko": "포털",      "kind": "ui", "module": "portal"},

    # Status card
    {"key": "status_title",   "ru": "Работает",   "en": "Live",      "ko": "실행 중",   "kind": "ui", "module": "portal"},
    {"key": "status_text",    "ru": "Работа и Финансы уже работают. Создавайте поездки, ведите учёт и управляйте бюджетом.",
                                   "en": "Work and Finance are live. Create rides, keep records and manage your budget.",
                                   "ko": "업무와 재정이 실행 중입니다. 출퇴근을 만들고, 기록을 관리하며 예산을 관리하세요.", "kind": "ui", "module": "portal"},
    {"key": "btn_open_money", "ru": "Открыть Финансы", "en": "Open Finance", "ko": "재정 열기", "kind": "ui", "module": "portal"},
    {"key": "btn_open_work",  "ru": "Открыть Работу",  "en": "Open Work",    "ko": "업무 열기", "kind": "ui", "module": "portal"},

    # Quick actions
    {"key": "quick_title",     "ru": "Быстрые действия", "en": "Quick actions", "ko": "빠른 작업", "kind": "ui", "module": "portal"},
    {"key": "quick_budget",    "ru": "Бюджет",     "en": "Budget",    "ko": "예산",      "kind": "ui", "module": "portal"},
    {"key": "quick_work",      "ru": "Работа",     "en": "Work",      "ko": "업무",      "kind": "ui", "module": "portal"},
    {"key": "quick_profile",   "ru": "Профиль",    "en": "Profile",   "ko": "프로필",    "kind": "ui", "module": "portal"},
    {"key": "quick_community", "ru": "Сообщества", "en": "Community", "ko": "커뮤니티",  "kind": "ui", "module": "portal"},

    # Sections
    {"key": "apps_title",   "ru": "Приложения Avalone",      "en": "Avalone apps",      "ko": "Avalone 앱",      "kind": "ui", "module": "portal"},
    {"key": "teaser_title", "ru": "Другие модули в планах",  "en": "More modules planned", "ko": "추가 모듈 계획 중", "kind": "ui", "module": "portal"},
    {"key": "teaser_text",  "ru": "Оставьте способ связи, и мы сообщим, когда модуль будет доступен.",
                                "en": "Leave your contact and we will notify you when the module is available.",
                                "ko": "연락처를 남기시면 모듈을 사용할 수 있게 되면 알려드립니다.", "kind": "ui", "module": "portal"},
    {"key": "teaser_placeholder", "ru": "Telegram / KakaoTalk / email", "en": "Telegram / KakaoTalk / email", "ko": "Telegram / KakaoTalk / email", "kind": "ui", "module": "portal"},
    {"key": "teaser_btn",   "ru": "Сообщить",   "en": "Notify me", "ko": "알림 받기", "kind": "ui", "module": "portal"},
    {"key": "footer",       "ru": "© Avalone — ваши инструменты в одном месте", "en": "© Avalone — your tools in one place", "ko": "© Avalone — 모든 도구가 한 곳에", "kind": "ui", "module": "portal"},

    # Bottom nav
    {"key": "nav_home",    "ru": "Портал",  "en": "Portal",  "ko": "포털",  "kind": "ui", "module": "portal"},
    {"key": "nav_money",   "ru": "Финансы", "en": "Finance", "ko": "재정",  "kind": "ui", "module": "portal"},
    {"key": "nav_chat",    "ru": "Чат",     "en": "Chat",    "ko": "채팅",  "kind": "ui", "module": "portal"},
    {"key": "nav_profile", "ru": "Профиль", "en": "Profile", "ko": "프로필", "kind": "ui", "module": "portal"},

    # Module nav (shared with Counta/Routa)
    {"key": "nav_trips",          "ru": "Поездки",    "en": "Trips",       "ko": "출퇴근", "kind": "ui", "module": "portal"},
    {"key": "nav_stats",          "ru": "Статистика", "en": "Statistics",  "ko": "통계",  "kind": "ui", "module": "portal"},
    {"key": "nav_notifications",  "ru": "Уведомления", "en": "Notifications", "ko": "알림", "kind": "ui", "module": "portal"},
    {"key": "nav_settings",       "ru": "Настройки",  "en": "Settings",    "ko": "설정",  "kind": "ui", "module": "portal"},
    {"key": "nav_balances",       "ru": "Остатки",    "en": "Balances",    "ko": "잔액",  "kind": "ui", "module": "portal"},
    {"key": "nav_journal",        "ru": "Журнал",     "en": "Journal",     "ko": "내역",  "kind": "ui", "module": "portal"},
    {"key": "nav_analytics",      "ru": "Аналитика",  "en": "Analytics",   "ko": "분석",  "kind": "ui", "module": "portal"},

    # Misc
    {"key": "coming_soon",        "ru": "В планах: ", "en": "Planned: ", "ko": "계획 중: ", "kind": "ui", "module": "portal"},
    {"key": "search_placeholder", "ru": "Поиск...",   "en": "Search...", "ko": "검색...",   "kind": "ui", "module": "portal"},
]

# Portal keys added during the hardcode-removal refactoring.
_PORTAL_SEED_EXTRA: list[dict[str, Any]] = [
    # Language selector
    {"key": "lang_selector_label", "ru": "Язык",      "en": "Language",  "ko": "언어", "kind": "ui", "module": "portal"},
    {"key": "lang_auto",           "ru": "Auto",      "en": "Auto",      "ko": "자동", "kind": "ui", "module": "portal"},
    {"key": "lang_ru",             "ru": "Русский",   "en": "Russian",   "ko": "러시아어", "kind": "ui", "module": "portal"},
    {"key": "lang_en",             "ru": "English",   "en": "English",   "ko": "영어", "kind": "ui", "module": "portal"},
    {"key": "lang_ko",             "ru": "한국어",     "en": "Korean",    "ko": "한국어", "kind": "ui", "module": "portal"},

    # Auth pages
    {"key": "auth_login_title",              "ru": "Вход",                                                "en": "Sign in",                                    "ko": "로그인", "kind": "ui", "module": "portal"},
    {"key": "auth_register_title",           "ru": "Регистрация",                                         "en": "Sign up",                                    "ko": "회원가입", "kind": "ui", "module": "portal"},
    {"key": "auth_label_login",              "ru": "Логин",                                               "en": "Username",                                   "ko": "아이디", "kind": "ui", "module": "portal"},
    {"key": "auth_label_password",           "ru": "Пароль",                                              "en": "Password",                                   "ko": "비밀번호", "kind": "ui", "module": "portal"},
    {"key": "auth_label_password2",          "ru": "Повторите пароль",                                    "en": "Confirm password",                           "ko": "비밀번호 확인", "kind": "ui", "module": "portal"},
    {"key": "auth_label_invite",             "ru": "Код приглашения (опционально)",                       "en": "Invite code (optional)",                     "ko": "초대 코드 (선택)", "kind": "ui", "module": "portal"},
    {"key": "auth_placeholder_login",        "ru": "Ваш логин",                                           "en": "Your username",                              "ko": "아이디", "kind": "ui", "module": "portal"},
    {"key": "auth_placeholder_password",     "ru": "••••••",                                              "en": "••••••",                                     "ko": "••••••", "kind": "ui", "module": "portal"},
    {"key": "auth_placeholder_password2",    "ru": "••••••",                                              "en": "••••••",                                     "ko": "••••••", "kind": "ui", "module": "portal"},
    {"key": "auth_placeholder_invite",       "ru": "код",                                                 "en": "code",                                       "ko": "코드", "kind": "ui", "module": "portal"},
    {"key": "auth_hint_password_min",        "ru": "Минимум 6 символов",                                  "en": "At least 6 characters",                      "ko": "최소 6자", "kind": "ui", "module": "portal"},
    {"key": "auth_btn_login",                "ru": "Войти",                                               "en": "Sign in",                                    "ko": "로그인", "kind": "ui", "module": "portal"},
    {"key": "auth_btn_register",             "ru": "Создать аккаунт",                                     "en": "Create account",                             "ko": "회원가입", "kind": "ui", "module": "portal"},
    {"key": "auth_no_account",               "ru": "Нет аккаунта?",                                       "en": "No account?",                                "ko": "계정이 없나요?", "kind": "ui", "module": "portal"},
    {"key": "auth_register_link",            "ru": "Зарегистрироваться",                                  "en": "Sign up",                                    "ko": "회원가입", "kind": "ui", "module": "portal"},
    {"key": "auth_has_account",              "ru": "Уже есть аккаунт?",                                   "en": "Already have an account?",                   "ko": "이미 계정이 있나요?", "kind": "ui", "module": "portal"},
    {"key": "auth_login_link",               "ru": "Войти",                                               "en": "Sign in",                                    "ko": "로그인", "kind": "ui", "module": "portal"},
    {"key": "auth_error_invalid_credentials","ru": "Неверный логин или пароль",                           "en": "Invalid username or password",               "ko": "아이디 또는 비밀번호가 잘못되었습니다", "kind": "ui", "module": "portal"},
    {"key": "auth_error_required",           "ru": "Логин и пароль обязательны",                          "en": "Username and password are required",         "ko": "아이디와 비밀번호를 입력하세요", "kind": "ui", "module": "portal"},
    {"key": "auth_error_password_mismatch",  "ru": "Пароли не совпадают",                                 "en": "Passwords do not match",                     "ko": "비밀번호가 일치하지 않습니다", "kind": "ui", "module": "portal"},
    {"key": "auth_error_password_too_short", "ru": "Пароль слишком короткий (минимум 6 символов)",        "en": "Password is too short (minimum 6 characters)", "ko": "비밀번호가 너무 짧습니다 (최소 6자)", "kind": "ui", "module": "portal"},
    {"key": "auth_error_login_taken",        "ru": "Этот логин уже занят",                                "en": "This username is already taken",             "ko": "이미 사용 중인 아이디입니다", "kind": "ui", "module": "portal"},

    # Generic API errors
    {"key": "error_unauthorized",            "ru": "Не авторизован",                                      "en": "Unauthorized",                               "ko": "인증되지 않음", "kind": "ui", "module": "portal"},
    {"key": "error_user_not_found",          "ru": "Пользователь не найден",                              "en": "User not found",                             "ko": "사용자를 찾을 수 없습니다", "kind": "ui", "module": "portal"},

    # Profile
    {"key": "profile_title",                 "ru": "Профиль",                                             "en": "Profile",                                    "ko": "프로필", "kind": "ui", "module": "portal"},
    {"key": "profile_email_missing",         "ru": "Email не указан",                                     "en": "No email set",                               "ko": "이메일 없음", "kind": "ui", "module": "portal"},
    {"key": "profile_section_security",      "ru": "Безопасность",                                        "en": "Security",                                   "ko": "보안", "kind": "ui", "module": "portal"},
    {"key": "profile_section_session",       "ru": "Сессия",                                              "en": "Session",                                    "ko": "세션", "kind": "ui", "module": "portal"},
    {"key": "profile_label_current_password","ru": "Текущий пароль",                                      "en": "Current password",                           "ko": "현재 비밀번호", "kind": "ui", "module": "portal"},
    {"key": "profile_label_new_password",    "ru": "Новый пароль",                                        "en": "New password",                               "ko": "새 비밀번호", "kind": "ui", "module": "portal"},
    {"key": "profile_label_new_password2",   "ru": "Повторите новый пароль",                              "en": "Confirm new password",                       "ko": "새 비밀번호 확인", "kind": "ui", "module": "portal"},
    {"key": "profile_btn_change_password",   "ru": "Сменить пароль",                                      "en": "Change password",                            "ko": "비밀번호 변경", "kind": "ui", "module": "portal"},
    {"key": "profile_btn_logout",            "ru": "Выйти",                                               "en": "Log out",                                    "ko": "로그아웃", "kind": "ui", "module": "portal"},
    {"key": "profile_password_mismatch",     "ru": "Новые пароли не совпадают",                           "en": "New passwords do not match",                 "ko": "새 비밀번호가 일치하지 않습니다", "kind": "ui", "module": "portal"},
    {"key": "profile_current_password_wrong","ru": "Текущий пароль неверный",                             "en": "Current password is wrong",                  "ko": "현재 비밀번호가 틀렸습니다", "kind": "ui", "module": "portal"},
    {"key": "profile_password_changed",      "ru": "Пароль изменён",                                      "en": "Password changed",                           "ko": "비밀번호가 변경되었습니다", "kind": "ui", "module": "portal"},

    # Shared shell
    {"key": "shell_apps_label",              "ru": "Приложения",                                          "en": "Apps",                                       "ko": "앱", "kind": "ui", "module": "portal"},
    {"key": "shell_search_label",            "ru": "Поиск",                                               "en": "Search",                                     "ko": "검색", "kind": "ui", "module": "portal"},
    {"key": "shell_search_placeholder",      "ru": "Поиск...",                                            "en": "Search...",                                  "ko": "검색...", "kind": "ui", "module": "portal"},
    {"key": "shell_search_close",            "ru": "Закрыть",                                             "en": "Close",                                      "ko": "닫기", "kind": "ui", "module": "portal"},
    {"key": "shell_theme_label",             "ru": "Тема",                                                "en": "Theme",                                      "ko": "테마", "kind": "ui", "module": "portal"},
    {"key": "shell_notifications_label",     "ru": "Уведомления",                                         "en": "Notifications",                              "ko": "알림", "kind": "ui", "module": "portal"},
    {"key": "shell_profile_label",           "ru": "Профиль",                                             "en": "Profile",                                    "ko": "프로필", "kind": "ui", "module": "portal"},
    {"key": "shell_profile_guest",           "ru": "Гость",                                               "en": "Guest",                                      "ko": "게스트", "kind": "ui", "module": "portal"},
    {"key": "shell_profile_profile",         "ru": "Профиль",                                             "en": "Profile",                                    "ko": "프로필", "kind": "ui", "module": "portal"},
    {"key": "shell_profile_login",           "ru": "Войти",                                               "en": "Sign in",                                    "ko": "로그인", "kind": "ui", "module": "portal"},
    {"key": "shell_profile_logout",          "ru": "Выйти",                                               "en": "Log out",                                    "ko": "로그아웃", "kind": "ui", "module": "portal"},
    {"key": "shell_status_in_dev",           "ru": "В разработке",                                        "en": "In development",                             "ko": "개발 중", "kind": "ui", "module": "portal"},
    {"key": "shell_status_planned",          "ru": "В планах",                                            "en": "Planned",                                    "ko": "계획 중", "kind": "ui", "module": "portal"},

    # PWA manifest
    {"key": "manifest_name",                 "ru": "Avalone",                                             "en": "Avalone",                                    "ko": "Avalone", "kind": "ui", "module": "portal"},
    {"key": "manifest_short_name",           "ru": "Avalone",                                             "en": "Avalone",                                    "ko": "Avalone", "kind": "ui", "module": "portal"},
    {"key": "manifest_description",          "ru": "Ваши инструменты в одном месте.",                     "en": "Your tools in one place.",                   "ko": "모든 도구가 한 곳에.", "kind": "ui", "module": "portal"},

    # PWA install hints
    {"key": "pwa_already_installed",         "ru": "Приложение уже установлено.",                         "en": "App is already installed.",                  "ko": "앱이 이미 설치되어 있습니다.", "kind": "ui", "module": "portal"},
    {"key": "pwa_install_ios_safari",        "ru": "На iPhone нажмите кнопку «Поделиться» внизу Safari, затем выберите «На экран «Домой»».",
                                                     "en": "On iPhone, tap the Share button at the bottom of Safari, then choose 'Add to Home Screen'.",
                                                     "ko": "iPhone에서는 Safari 하단의 공유 버튼을 누르고 '홈 화면에 추가'를 선택하세요.", "kind": "ui", "module": "portal"},
    {"key": "pwa_install_ios_other",         "ru": "На iPhone PWA устанавливается только через Safari. Откройте сайт в Safari и нажмите «Поделиться» → «На экран «Домой»».",
                                                     "en": "On iPhone, PWA can only be installed via Safari. Open the site in Safari and tap Share → Add to Home Screen.",
                                                     "ko": "iPhone에서는 Safari를 통해서만 PWA를 설치할 수 있습니다. Safari에서 사이트를 열고 공유 → 홈 화면에 추가를 누르세요.", "kind": "ui", "module": "portal"},
    {"key": "pwa_install_android",           "ru": "Чтобы установить, нажмите «⋮» в Chrome и выберите «Добавить на главный экран».",
                                                     "en": "To install, tap '⋮' in Chrome and choose 'Add to Home Screen'.",
                                                     "ko": "설치하려면 Chrome에서 '⋮'를 누르고 '홈 화면에 추가'를 선택하세요.", "kind": "ui", "module": "portal"},
    {"key": "pwa_install_desktop",           "ru": "Чтобы установить, нажмите в браузере «⋯» → «Приложения» → «Установить Avalone» (Chrome/Edge).",
                                                     "en": "To install, tap '⋯' in the browser, then Apps → Install Avalone (Chrome/Edge).",
                                                     "ko": "설치하려면 브라우저에서 '⋯' → 앱 → Avalone 설치를 선택하세요 (Chrome/Edge).", "kind": "ui", "module": "portal"},

    # Search / waitlist
    {"key": "search_result_prefix",          "ru": "Вы искали: ",                                         "en": "You searched: ",                             "ko": "검색: ", "kind": "ui", "module": "portal"},
    {"key": "waitlist_thanks_prefix",        "ru": "Спасибо! Мы запомнили: ",                             "en": "Thanks! We saved: ",                         "ko": "감사합니다! 저장했습니다: ", "kind": "ui", "module": "portal"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema() -> None:
    with connection() as con:
        con.executescript(SCHEMA)


def upsert(key: str, ru: str = "", en: str = "", ko: str = "", kind: str = "ui",
           module: str = "", desc: str | None = None) -> None:
    upsert_many([{"key": key, "ru": ru, "en": en, "ko": ko,
                  "kind": kind, "module": module, "desc": desc}])


def upsert_many(rows: list[dict[str, Any]]) -> int:
    """Insert or update rows. desc=None means "do not overwrite existing desc".
    desc="" explicitly clears it. Returns number of processed rows."""
    with connection() as con:
        for r in rows:
            desc = r.get("desc")
            now = _now()
            params = (
                r["key"],
                r.get("ru", ""),
                r.get("en", ""),
                r.get("ko", ""),
                r.get("kind", "ui"),
                r.get("module", ""),
                desc if desc is not None else "",
                now,
            )
            if desc is None:
                con.execute(
                    "INSERT INTO avalone_glossary "
                    "(key, ru, en, ko, kind, module, desc, updated_at) VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET "
                    "ru=excluded.ru, en=excluded.en, ko=excluded.ko, "
                    "kind=excluded.kind, module=excluded.module, updated_at=excluded.updated_at "
                    "WHERE excluded.ru<>avalone_glossary.ru OR excluded.en<>avalone_glossary.en "
                    "OR excluded.ko<>avalone_glossary.ko OR excluded.kind<>avalone_glossary.kind "
                    "OR excluded.module<>avalone_glossary.module",
                    params,
                )
            else:
                con.execute(
                    "INSERT INTO avalone_glossary "
                    "(key, ru, en, ko, kind, module, desc, updated_at) VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET "
                    "ru=excluded.ru, en=excluded.en, ko=excluded.ko, "
                    "kind=excluded.kind, module=excluded.module, desc=excluded.desc, "
                    "updated_at=excluded.updated_at",
                    params,
                )
    return len(rows)


def set_desc(key: str, desc: str) -> None:
    with connection() as con:
        con.execute(
            "UPDATE avalone_glossary SET desc=?, updated_at=? WHERE key=?",
            (desc, _now(), key),
        )


def touch(key: str) -> None:
    with connection() as con:
        con.execute("UPDATE avalone_glossary SET updated_at=? WHERE key=?", (_now(), key))


def get(key: str, lang: str = "ru") -> str:
    """Translate key; fallback ru -> en -> key."""
    with connection() as con:
        row = con.execute(
            "SELECT ru, en, ko FROM avalone_glossary WHERE key=?", (key,)
        ).fetchone()
    if not row:
        return key
    vals = {"ru": row["ru"], "en": row["en"], "ko": row["ko"]}
    return vals.get(lang) or vals["ru"] or vals["en"] or key


# Alias used in templates and registry.
t = get


def all_by_lang(kind: str | None = None, module: str | None = None) -> dict[str, dict[str, str]]:
    """{lang: {key: text}} convenient for front-end bootstrapping."""
    out: dict[str, dict[str, str]] = {l: {} for l in LANGS}
    where: list[str] = []
    params: list[Any] = []
    if kind:
        where.append("kind=?")
        params.append(kind)
    if module:
        where.append("module=?")
        params.append(module)
    sql = "SELECT key, ru, en, ko FROM avalone_glossary"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with connection() as con:
        for row in con.execute(sql, params):
            vals = {"ru": row["ru"], "en": row["en"], "ko": row["ko"]}
            for l in LANGS:
                if vals.get(l):
                    out[l][row["key"]] = vals[l]
    return out


def i18n_js() -> dict[str, dict[str, str]]:
    """Backwards-compatible alias for Jinja global."""
    return all_by_lang()


def entries(kind: str | None = None, module: str | None = None) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if kind:
        where.append("kind=?")
        params.append(kind)
    if module:
        where.append("module=?")
        params.append(module)
    sql = "SELECT key, ru, en, ko, kind, module, desc FROM avalone_glossary"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY module, kind, key"
    with connection() as con:
        rows = con.execute(sql, params).fetchall()
    return [{
        "key": r["key"],
        "ru": r["ru"] or "",
        "en": r["en"] or "",
        "ko": r["ko"] or "",
        "kind": r["kind"] or "ui",
        "module": r["module"] or "",
        "desc": r["desc"] or "",
    } for r in rows]


def describe(key: str) -> str:
    with connection() as con:
        row = con.execute("SELECT desc FROM avalone_glossary WHERE key=?", (key,)).fetchone()
    return (row["desc"] if row and row["desc"] else "")


def missing_desc(kind: str | None = None, module: str | None = None) -> list[str]:
    where = ["(desc IS NULL OR desc='')"]
    params: list[Any] = []
    if kind:
        where.append("kind=?")
        params.append(kind)
    if module:
        where.append("module=?")
        params.append(module)
    sql = "SELECT key FROM avalone_glossary WHERE " + " AND ".join(where) + " ORDER BY module, kind, key"
    with connection() as con:
        return [r["key"] for r in con.execute(sql, params)]


def count(kind: str | None = None, module: str | None = None) -> int:
    where: list[str] = []
    params: list[Any] = []
    if kind:
        where.append("kind=?")
        params.append(kind)
    if module:
        where.append("module=?")
        params.append(module)
    sql = "SELECT COUNT(*) FROM avalone_glossary"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with connection() as con:
        return con.execute(sql, params).fetchone()[0]


def _legacy_table_exists(con: sqlite3.Connection, name: str) -> bool:
    r = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return r is not None


def _merge_legacy(con: sqlite3.Connection, table: str, module: str) -> int:
    """Copy rows from a legacy per-app glossary table into avalone_glossary,
    merging translations and descriptions without overwriting non-empty values."""
    if not _legacy_table_exists(con, table):
        return 0
    rows = con.execute(
        f"SELECT key, ru, en, ko, kind, desc FROM {table}"
    ).fetchall()
    merged = 0
    for r in rows:
        key, ru, en, ko, kind, desc = r
        existing = con.execute(
            "SELECT ru, en, ko, desc FROM avalone_glossary WHERE key=?", (key,)
        ).fetchone()
        if existing:
            eru, een, eko, edesc = existing
            ru = ru or eru or ""
            en = en or een or ""
            ko = ko or eko or ""
            desc = desc or edesc or ""
            con.execute(
                "UPDATE avalone_glossary SET ru=?, en=?, ko=?, kind=COALESCE(NULLIF(?,''),kind), "
                "module=COALESCE(NULLIF(?,''),module), desc=? WHERE key=?",
                (ru, en, ko, kind, module, desc, key),
            )
        else:
            con.execute(
                "INSERT INTO avalone_glossary (key, ru, en, ko, kind, module, desc, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (key, ru or "", en or "", ko or "", kind or "ui", module, desc or "", _now()),
            )
        merged += 1
    return merged


def migrate_legacy() -> dict[str, int]:
    """Migrate money_glossary and work_glossary into avalone_glossary.
    Safe to call multiple times; idempotent merge."""
    with connection() as con:
        n_money = _merge_legacy(con, "money_glossary", "money")
        n_work = _merge_legacy(con, "work_glossary", "work")
    return {"money": n_money, "work": n_work}


def seed_portal() -> int:
    """Seed portal/shared keys. Idempotent: preserves existing desc if already set."""
    from avalone_core.ui_glossary import describe as ui_describe
    rows = []
    for row in _PORTAL_SEED + _PORTAL_SEED_EXTRA:
        d = dict(row)
        d.setdefault("desc", ui_describe(row["key"]))
        rows.append(d)
    return upsert_many(rows)


def apply_descriptions() -> int:
    """Fill empty desc values for UI keys using ui_glossary rules."""
    from avalone_core.ui_glossary import describe as ui_describe
    updated = 0
    with connection() as con:
        keys = [r["key"] for r in con.execute(
            "SELECT key FROM avalone_glossary WHERE (desc IS NULL OR desc='')"
        )]
    for key in keys:
        d = ui_describe(key)
        if d:
            set_desc(key, d)
            updated += 1
    return updated


def migrate() -> dict[str, Any]:
    """Run schema creation, legacy migration, portal seed, and description backfill.
    Called from avalone_core.db.migrate() on every app startup."""
    ensure_schema()
    legacy = migrate_legacy()
    portal = seed_portal()
    described = apply_descriptions()
    return {"legacy": legacy, "portal": portal, "described": described}


def audit() -> dict[str, Any]:
    """Human-readable summary for CLI/debugging."""
    return {
        "total": count(),
        "missing_desc": missing_desc(),
        "by_module": {
            module: count(module=module)
            for module in ("portal", "money", "work")
        },
    }
