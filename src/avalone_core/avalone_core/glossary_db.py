"""Backward-compatible facade over GlossaryRepository.

This module no longer contains raw SQL. All database operations live in
`GlossaryRepository` (avalone_core.glossary_service). It keeps the portal seed
data and re-exports the original functional API plus the class API for
convenience.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from avalone_core.glossary_service import SCHEMA, GlossaryRepository

LANGS = ("ru", "en", "ko")

# Seed data for the portal / shared shell. Domain keys (Avalone Finance/Avalone Work categories,
# currencies, etc.) are migrated from legacy tables or seeded by the apps.
_PORTAL_SEED: list[dict[str, Any]] = [
    # Apps
    {"key": "app_money",      "ru": "Финансы",    "en": "Finance",   "ko": "재정",      "kind": "ui", "module": "portal"},
    {"key": "app_education",  "ru": "Обучение",   "en": "Education", "ko": "교육",      "kind": "ui", "module": "portal"},
    {"key": "app_living",     "ru": "Жильё",      "en": "Living",    "ko": "주거",      "kind": "ui", "module": "portal"},
    {"key": "app_travel",     "ru": "Поездки",    "en": "Travel",    "ko": "여행",      "kind": "ui", "module": "portal"},
    {"key": "app_health",     "ru": "Здоровье",   "en": "Health",    "ko": "건강",      "kind": "ui", "module": "portal"},

    # App descriptions
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
    {"key": "status_text",    "ru": "Финансы уже работают. Ведите учёт и управляйте бюджетом.",
                                   "en": "Finance is live. Keep records and manage your budget.",
                                   "ko": "재정이 실행 중입니다. 기록을 관리하며 예산을 관리하세요.", "kind": "ui", "module": "portal"},
    {"key": "btn_open_money", "ru": "Открыть Финансы", "en": "Open Finance", "ko": "재정 열기", "kind": "ui", "module": "portal"},

    # Quick actions
    {"key": "quick_title",     "ru": "Быстрые действия", "en": "Quick actions", "ko": "빠른 작업", "kind": "ui", "module": "portal"},
    {"key": "quick_budget",    "ru": "Бюджет",     "en": "Budget",    "ko": "예산",      "kind": "ui", "module": "portal"},
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
    {"key": "feedback_title",         "ru": "Сообщение авторам",                           "en": "Message to the authors",                    "ko": "작성자에게 메시지", "kind": "ui", "module": "portal"},
    {"key": "feedback_text",          "ru": "Расскажите, что важно для вас, или задайте вопрос. Мы читаем всё.",
                                            "en": "Tell us what matters to you or ask a question. We read everything.",
                                            "ko": "중요한 점이나 질문을 남겨주세요. 모두 읽고 있습니다.", "kind": "ui", "module": "portal"},
    {"key": "feedback_contact_label", "ru": "Как с вами связаться (необязательно)",         "en": "How to reach you (optional)",               "ko": "연락처 (선택)", "kind": "ui", "module": "portal"},
    {"key": "feedback_message_label", "ru": "Сообщение",                                   "en": "Message",                                   "ko": "메시지", "kind": "ui", "module": "portal"},
    {"key": "feedback_contact_placeholder","ru": "Telegram / KakaoTalk / email",            "en": "Telegram / KakaoTalk / email",              "ko": "Telegram / KakaoTalk / email", "kind": "ui", "module": "portal"},
    {"key": "feedback_message_placeholder","ru": "Ваше сообщение...",                       "en": "Your message...",                           "ko": "메시지를 입력하세요...", "kind": "ui", "module": "portal"},
    {"key": "feedback_btn",           "ru": "Отправить",                                   "en": "Send",                                      "ko": "전송", "kind": "ui", "module": "portal"},

    {"key": "feedback_thanks",        "ru": "Спасибо, сообщение отправлено.",              "en": "Thank you, your message has been sent.",    "ko": "메시지가 전송되었습니다. 감사합니다.", "kind": "ui", "module": "portal"},
    {"key": "feedback_error",         "ru": "Не удалось отправить. Попробуйте ещё раз.",   "en": "Could not send. Please try again.",         "ko": "전송하지 못했습니다. 다시 시도해주세요.", "kind": "ui", "module": "portal"},
    {"key": "footer",       "ru": "© Avalone — ваши инструменты в одном месте", "en": "© Avalone — your tools in one place", "ko": "© Avalone — 모든 도구가 한 곳에", "kind": "ui", "module": "portal"},

    # Bottom nav
    {"key": "nav_home",    "ru": "Портал",  "en": "Portal",  "ko": "포털",  "kind": "ui", "module": "portal"},
    {"key": "nav_money",   "ru": "Финансы", "en": "Finance", "ko": "재정",  "kind": "ui", "module": "portal"},
    {"key": "nav_chat",    "ru": "Чат",     "en": "Chat",    "ko": "채팅",  "kind": "ui", "module": "portal"},
    {"key": "nav_profile", "ru": "Профиль", "en": "Profile", "ko": "프로필", "kind": "ui", "module": "portal"},

    # Module nav (shared with Avalone Finance/Avalone Work)
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

    # Password reset
    {"key": "reset_forgot_title",            "ru": "Восстановление пароля",                               "en": "Password recovery",                          "ko": "비밀번호 복구", "kind": "ui", "module": "portal"},
    {"key": "reset_forgot_hint",             "ru": "Введите логин или email, и мы пришлём ссылку для сброса пароля.",
                                                       "en": "Enter your username or email and we'll send a reset link.",
                                                       "ko": "로그인 또는 이메일을 입력하면 비밀번호 재설정 링크를 본내드립니다.", "kind": "ui", "module": "portal"},
    {"key": "reset_label_login_or_email",    "ru": "Логин или email",                                     "en": "Username or email",                          "ko": "로그인 또는 이메일", "kind": "ui", "module": "portal"},
    {"key": "reset_placeholder_login_or_email", "ru": "lucifer или email",                                "en": "lucifer or email",                           "ko": "lucifer 또는 이메일", "kind": "ui", "module": "portal"},
    {"key": "reset_btn_send",                "ru": "Отправить ссылку",                                    "en": "Send link",                                  "ko": "링크 본내기", "kind": "ui", "module": "portal"},
    {"key": "reset_email_subject",           "ru": "Сброс пароля Avalone",                                "en": "Avalone password reset",                     "ko": "Avalone 비밀번호 재설정", "kind": "ui", "module": "portal"},
    {"key": "reset_email_body",              "ru": "Привет, {login}.\n\nКто-то запросил сброс пароля для аккаунта Avalone. Перейдите по ссылке, чтобы задать новый пароль:\n\n{url}\n\nСсылка действительна 1 час. Если это были не вы, просто проигнорируйте письмо.",
                                                       "en": "Hi {login},\n\nSomeone requested a password reset for your Avalone account. Use the link below to set a new password:\n\n{url}\n\nThis link is valid for 1 hour. If you didn't request this, please ignore this email.",
                                                       "ko": "안녕하세요 {login}님,\n\nAvalone 계정의 비밀번호 재설정이 요청되었습니다. 아래 링크를 클릭하여 새 비밀번호를 설정하세요:\n\n{url}\n\n링크는 1시간 동안 유효합니다. 요청하신 적이 없다면 이 메일을 무시하세요.", "kind": "ui", "module": "portal"},
    {"key": "reset_email_sent",              "ru": "Ссылка отправлена на ваш email.",                     "en": "Link sent to your email.",                   "ko": "이메일로 링크를 본냈습니다.", "kind": "ui", "module": "portal"},
    {"key": "reset_email_failed",            "ru": "Не удалось отправить письмо: {error}",                "en": "Failed to send email: {error}",              "ko": "이메일 전송 실패: {error}", "kind": "ui", "module": "portal"},
    {"key": "reset_email_sent_no_email",     "ru": "Аккаунт найден, но email не указан. Свяжитесь с поддержкой.",
                                                       "en": "Account found, but no email is set. Please contact support.",
                                                       "ko": "계정은 찾았지만 이메일이 설정되어 있지 않습니다. 지원팀에 문의하세요.", "kind": "ui", "module": "portal"},
    {"key": "reset_email_sent_generic",      "ru": "Если указанный аккаунт существует, ссылка отправлена на email.",
                                                       "en": "If the account exists, a reset link has been sent.",
                                                       "ko": "계정이 존재할 경우 이메일로 링크를 본냈습니다.", "kind": "ui", "module": "portal"},
    {"key": "reset_error_required",          "ru": "Укажите логин или email.",                            "en": "Please enter your username or email.",       "ko": "로그인 또는 이메일을 입력하세요.", "kind": "ui", "module": "portal"},
    {"key": "reset_dev_link_prefix",         "ru": "Почтовая служба не настроена — используйте ссылку ниже (dev only):",
                                                       "en": "Mail is not configured — use the link below (dev only):",
                                                       "ko": "메일이 설정되지 않았습니다. 아래 링크를 사용하세요(개발 전용):", "kind": "ui", "module": "portal"},
    {"key": "reset_title",                   "ru": "Новый пароль",                                        "en": "New password",                               "ko": "새 비밀번호", "kind": "ui", "module": "portal"},
    {"key": "reset_btn_save",                "ru": "Сохранить пароль",                                    "en": "Save password",                              "ko": "비밀번호 저장", "kind": "ui", "module": "portal"},
    {"key": "reset_token_missing",           "ru": "Ссылка для сброса не действительна или устарела.",    "en": "Reset link is invalid or expired.",          "ko": "재설정 링크가 유효하지 않거나 만료되었습니다.", "kind": "ui", "module": "portal"},
    {"key": "reset_token_invalid",           "ru": "Ссылка устарела или недействительна. Запросите новую.",
                                                       "en": "This link is expired or invalid. Please request a new one.",
                                                       "ko": "링크가 만료되었거나 유효하지 않습니다. 새로 요청하세요.", "kind": "ui", "module": "portal"},
    {"key": "reset_password_success",        "ru": "Пароль изменён. Войдите с новым паролем.",            "en": "Password updated. Please sign in with your new password.",
                                                       "ko": "비밀번호가 변경되었습니다. 새 비밀번호로 로그인하세요.", "kind": "ui", "module": "portal"},
    {"key": "reset_forgot_link",             "ru": "Забыли пароль?",                                      "en": "Forgot password?",                           "ko": "비밀번호를 잊으셨나요?", "kind": "ui", "module": "portal"},

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
    {"key": "profile_section_identity",      "ru": "Личные данные",                                       "en": "Identity",                                   "ko": "개인 정보", "kind": "ui", "module": "portal"},
    {"key": "profile_name_label",            "ru": "Отображаемое имя",                                    "en": "Display name",                               "ko": "표시 이름", "kind": "ui", "module": "portal"},
    {"key": "profile_name_placeholder",      "ru": "Как к вам обращаться",                                "en": "How should we address you",                  "ko": "어떻게 불러드릴까요", "kind": "ui", "module": "portal"},
    {"key": "profile_btn_save_name",         "ru": "Сохранить имя",                                       "en": "Save name",                                  "ko": "이름 저장", "kind": "ui", "module": "portal"},
    {"key": "profile_email_label",           "ru": "Email",                                               "en": "Email",                                      "ko": "이메일", "kind": "ui", "module": "portal"},
    {"key": "profile_email_placeholder",     "ru": "you@example.com",                                     "en": "you@example.com",                            "ko": "you@example.com", "kind": "ui", "module": "portal"},
    {"key": "profile_email_verified",        "ru": "Подтверждён",                                         "en": "Verified",                                   "ko": "인증됨", "kind": "ui", "module": "portal"},
    {"key": "profile_email_unverified",      "ru": "Не подтверждён",                                      "en": "Unverified",                                 "ko": "미인증", "kind": "ui", "module": "portal"},
    {"key": "profile_btn_change_email",      "ru": "Сменить email",                                       "en": "Change email",                               "ko": "이메일 변경", "kind": "ui", "module": "portal"},
    {"key": "profile_btn_send_code",         "ru": "Выслать код подтверждения",                           "en": "Send verification code",                     "ko": "인증 코드 본내기", "kind": "ui", "module": "portal"},
    {"key": "profile_btn_verify",            "ru": "Подтвердить",                                         "en": "Verify",                                     "ko": "인증", "kind": "ui", "module": "portal"},
    {"key": "profile_verify_code_label",     "ru": "Код из письма",                                       "en": "Code from email",                            "ko": "이메일 인증 코드", "kind": "ui", "module": "portal"},
    {"key": "profile_verify_email_subject",  "ru": "Подтверждение email в Avalone",                       "en": "Avalone email verification",                 "ko": "Avalone 이메일 인증", "kind": "ui", "module": "portal"},
    {"key": "profile_verify_email_body",     "ru": "Ваш код подтверждения: {code}\nВведите его в профиле.", "en": "Your verification code: {code}\nEnter it in your profile.", "ko": "인증 코드: {code}\n프로필에 입력하세요.", "kind": "ui", "module": "portal"},
    {"key": "profile_verify_email_sent",     "ru": "Код подтверждения отправлен",                         "en": "Verification code sent",                     "ko": "인증 코드가 발송되었습니다", "kind": "ui", "module": "portal"},
    {"key": "profile_verify_email_send_failed","ru": "Не удалось отправить код: {error}",                   "en": "Failed to send code: {error}",               "ko": "코드 발송 실패: {error}", "kind": "ui", "module": "portal"},
    {"key": "profile_verify_email_invalid",  "ru": "Неверный или просроченный код",                       "en": "Invalid or expired code",                    "ko": "잘못되었거나 만료된 코드", "kind": "ui", "module": "portal"},
    {"key": "profile_email_verified_success","ru": "Email подтверждён",                                   "en": "Email verified",                             "ko": "이메일이 인증되었습니다", "kind": "ui", "module": "portal"},
    {"key": "profile_email_invalid",         "ru": "Укажите корректный email",                            "en": "Please enter a valid email",                 "ko": "올바른 이메일을 입력하세요", "kind": "ui", "module": "portal"},
    {"key": "profile_password_label",        "ru": "Пароль",                                              "en": "Password",                                   "ko": "비밀번호", "kind": "ui", "module": "portal"},
    {"key": "profile_password_masked",       "ru": "••••••",                                              "en": "••••••",                                     "ko": "••••••", "kind": "ui", "module": "portal"},
    {"key": "profile_btn_reset_password",    "ru": "Сбросить пароль",                                     "en": "Reset password",                             "ko": "비밀번호 재설정", "kind": "ui", "module": "portal"},
    {"key": "profile_reset_title",           "ru": "Сброс пароля",                                        "en": "Reset password",                             "ko": "비밀번호 재설정", "kind": "ui", "module": "portal"},
    {"key": "profile_reset_text",            "ru": "Мы вышлем ссылку для сброса на {email}. Перейдите по ней и задайте новый пароль.",
                                                       "en": "We will send a reset link to {email}. Follow it to set a new password.",
                                                       "ko": "{email}로 재설정 링크를 복사합니다. 링크를 따라 새 비밀번호를 설정하세요.", "kind": "ui", "module": "portal"},
    {"key": "profile_reset_btn_send",        "ru": "Выслать ссылку",                                      "en": "Send reset link",                            "ko": "재설정 링크 복사", "kind": "ui", "module": "portal"},
    {"key": "profile_reset_sent",            "ru": "Ссылка для сброса отправлена. Проверьте почту.",      "en": "Reset link sent. Please check your email.",  "ko": "재설정 링크가 발송되었습니다. 이메일을 확인하세요.", "kind": "ui", "module": "portal"},
    {"key": "profile_reset_send_failed",     "ru": "Не удалось отправить ссылку: {error}",                "en": "Failed to send reset link: {error}",         "ko": "재설정 링크 발송 실패: {error}", "kind": "ui", "module": "portal"},
    {"key": "profile_reset_email_required",  "ru": "Чтобы сбросить пароль, сначала подтвердите email в профиле.",
                                                       "en": "To reset your password, please verify your email in the profile first.",
                                                       "ko": "비밀번호를 재설정하려면 먼저 프로필에서 이메일을 인증하세요.", "kind": "ui", "module": "portal"},

    # Shared shell
    {"key": "shell_menu_title",              "ru": "Меню Avalone",                                        "en": "Avalone menu",                               "ko": "Avalone 메뉴", "kind": "ui", "module": "portal"},
    {"key": "shell_nav_home",                "ru": "Портал",                                              "en": "Portal",                                     "ko": "포털", "kind": "ui", "module": "portal"},
    {"key": "shell_apps_label",              "ru": "Приложения",                                          "en": "Apps",                                       "ko": "앱", "kind": "ui", "module": "portal"},
    {"key": "shell_search_label",            "ru": "Поиск",                                               "en": "Search",                                     "ko": "검색", "kind": "ui", "module": "portal"},
    {"key": "shell_search_placeholder",      "ru": "Поиск...",                                            "en": "Search...",                                  "ko": "검색...", "kind": "ui", "module": "portal"},
    {"key": "shell_search_close",            "ru": "Закрыть",                                             "en": "Close",                                      "ko": "닫기", "kind": "ui", "module": "portal"},
    {"key": "shell_theme_label",             "ru": "Тема",                                                "en": "Theme",                                      "ko": "테마", "kind": "ui", "module": "portal"},
    {"key": "shell_language_label",          "ru": "Язык",                                                "en": "Language",                                   "ko": "언어", "kind": "ui", "module": "portal"},
    {"key": "shell_notifications_label",     "ru": "Уведомления",                                         "en": "Notifications",                              "ko": "알림", "kind": "ui", "module": "portal"},
    {"key": "shell_profile_label",           "ru": "Профиль",                                             "en": "Profile",                                    "ko": "프로필", "kind": "ui", "module": "portal"},
    {"key": "shell_profile_guest",           "ru": "Гость",                                               "en": "Guest",                                      "ko": "게스트", "kind": "ui", "module": "portal"},
    {"key": "shell_profile_profile",         "ru": "Профиль",                                             "en": "Profile",                                    "ko": "프로필", "kind": "ui", "module": "portal"},
    {"key": "shell_profile_login",           "ru": "Войти",                                               "en": "Sign in",                                    "ko": "로그인", "kind": "ui", "module": "portal"},
    {"key": "shell_profile_logout",          "ru": "Выйти",                                               "en": "Log out",                                    "ko": "로그아웃", "kind": "ui", "module": "portal"},
    {"key": "shell_status_in_dev",           "ru": "В разработке",                                        "en": "In development",                             "ko": "개발 중", "kind": "ui", "module": "portal"},
    {"key": "shell_status_planned",          "ru": "В планах",                                            "en": "Planned",                                    "ko": "계획 중", "kind": "ui", "module": "portal"},
    {"key": "shell_close_menu",              "ru": "Закрыть меню",                                        "en": "Close menu",                                 "ko": "메뉴 닫기", "kind": "ui", "module": "portal"},
    {"key": "shell_share_app",               "ru": "Пригласить друзей",                                   "en": "Invite friends",                             "ko": "친구 초대", "kind": "ui", "module": "portal"},
    {"key": "shell_invite_title",            "ru": "Пригласить друга в Avalone",                          "en": "Invite a friend to Avalone",                 "ko": "Avalone에 친구 초대", "kind": "ui", "module": "portal"},
    {"key": "shell_invite_share_btn",        "ru": "Поделиться",                                          "en": "Share",                                      "ko": "공유", "kind": "ui", "module": "portal"},
    {"key": "shell_invite_copy_btn",         "ru": "Копировать ссылку",                                   "en": "Copy link",                                  "ko": "링크 복사", "kind": "ui", "module": "portal"},
    {"key": "shell_invite_qr_alt",           "ru": "QR-код для приглашения",                              "en": "Invitation QR code",                         "ko": "초대 QR 코드", "kind": "ui", "module": "portal"},
    {"key": "shell_admin_link",              "ru": "Администрирование",                                   "en": "Administration",                             "ko": "관리", "kind": "ui", "module": "portal"},
    {"key": "shell_login",                   "ru": "Войти",                                               "en": "Sign in",                                    "ko": "로그인", "kind": "ui", "module": "portal"},
    {"key": "shell_login_other",             "ru": "Войти в другой аккаунт",                              "en": "Sign in to another account",                 "ko": "다른 계정으로 로그인", "kind": "ui", "module": "portal"},
    {"key": "auth_already_active",           "ru": "Вы уже вошли в этот аккаунт.",                        "en": "You are already signed in to this account.", "ko": "이미 이 계정으로 로그인되어 있습니다.", "kind": "ui", "module": "portal"},
    {"key": "auth_currently_signed_in_as",   "ru": "Сейчас вы вошли как",                                 "en": "You are currently signed in as",             "ko": "현재 로그인된 계정", "kind": "ui", "module": "portal"},
    {"key": "auth_add_account_hint",         "ru": "Можете войти в другой, чтобы добавить его в список.", "en": "You can sign in to another one to add it to the list.", "ko": "목록에 추가하려면 다른 계정으로 로그인하세요.", "kind": "ui", "module": "portal"},
    {"key": "shell_logout",                  "ru": "Выйти",                                               "en": "Log out",                                    "ko": "로그아웃", "kind": "ui", "module": "portal"},
    {"key": "shell_profile",                 "ru": "Профиль",                                             "en": "Profile",                                    "ko": "프로필", "kind": "ui", "module": "portal"},
    {"key": "shell_feedback",                "ru": "Сообщение авторам",                                   "en": "Message to authors",                         "ko": "작성자에게 메시지", "kind": "ui", "module": "portal"},
    {"key": "shell_active_profile",          "ru": "активен",                                             "en": "active",                                     "ko": "활성", "kind": "ui", "module": "portal"},

    # PWA manifest
    {"key": "manifest_name",                 "ru": "Avalone",                                             "en": "Avalone",                                    "ko": "Avalone", "kind": "ui", "module": "portal"},
    {"key": "manifest_short_name",           "ru": "Avalone",                                             "en": "Avalone",                                    "ko": "Avalone", "kind": "ui", "module": "portal"},
    {"key": "manifest_description",          "ru": "Ваши инструменты в одном месте.",                     "en": "Your tools in one place.",                   "ko": "모든 도구가 한 곳에.", "kind": "ui", "module": "portal"},

    # PWA install hints
    {"key": "install_app",                   "ru": "📲 Установить приложение",                            "en": "📲 Install app",                             "ko": "📲 앱 설치", "kind": "ui", "module": "portal"},
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

    # Button feedback states
    {"key": "ui_sending",                    "ru": "Отправка...",                                         "en": "Sending...",                                 "ko": "전송 중...", "kind": "ui", "module": "portal"},
    {"key": "ui_sent",                       "ru": "Отправлено",                                          "en": "Sent",                                       "ko": "전송 완료", "kind": "ui", "module": "portal"},
    {"key": "ui_error",                      "ru": "Ошибка",                                              "en": "Error",                                      "ko": "오류", "kind": "ui", "module": "portal"},

    # Search / waitlist
    {"key": "search_result_prefix",          "ru": "Вы искали: ",                                         "en": "You searched: ",                             "ko": "검색: ", "kind": "ui", "module": "portal"},
    {"key": "waitlist_thanks_prefix",        "ru": "Спасибо! Мы запомнили: ",                             "en": "Thanks! We saved: ",                         "ko": "감사합니다! 저장했습니다: ", "kind": "ui", "module": "portal"},

    # Admin panel
    {"key": "admin_title",                   "ru": "Администрирование",                                   "en": "Administration",                             "ko": "관리", "kind": "ui", "module": "portal"},
    {"key": "admin_menu_dashboard",          "ru": "Обзор",                                               "en": "Dashboard",                                  "ko": "대시보드", "kind": "ui", "module": "portal"},
    {"key": "admin_menu_users",              "ru": "Пользователи",                                        "en": "Users",                                      "ko": "사용자", "kind": "ui", "module": "portal"},
    {"key": "admin_menu_settings",           "ru": "Настройки сервера",                                   "en": "Server settings",                            "ko": "서버 설정", "kind": "ui", "module": "portal"},
    {"key": "admin_menu_feedback",           "ru": "Обратная связь",                                      "en": "Feedback",                                   "ko": "피드백", "kind": "ui", "module": "portal"},
    {"key": "admin_feedback_title",          "ru": "Обратная связь",                                      "en": "Feedback",                                   "ko": "피드백", "kind": "ui", "module": "portal"},
    {"key": "admin_feedback_list_title",     "ru": "Сообщения",                                           "en": "Messages",                                   "ko": "메시지", "kind": "ui", "module": "portal"},
    {"key": "admin_feedback_col_time",       "ru": "Когда",                                               "en": "When",                                       "ko": "시간", "kind": "ui", "module": "portal"},
    {"key": "admin_feedback_col_user",       "ru": "Пользователь",                                        "en": "User",                                       "ko": "사용자", "kind": "ui", "module": "portal"},
    {"key": "admin_feedback_col_contact",    "ru": "Контакт",                                             "en": "Contact",                                    "ko": "연락처", "kind": "ui", "module": "portal"},
    {"key": "admin_feedback_col_message",    "ru": "Сообщение",                                           "en": "Message",                                    "ko": "메시지", "kind": "ui", "module": "portal"},
    {"key": "admin_feedback_col_source",     "ru": "Источник",                                            "en": "Source",                                     "ko": "출처", "kind": "ui", "module": "portal"},
    {"key": "admin_feedback_anonymous",      "ru": "аноним",                                              "en": "anonymous",                                  "ko": "익명", "kind": "ui", "module": "portal"},
    {"key": "admin_feedback_empty",          "ru": "Пока нет сообщений.",                                 "en": "No messages yet.",                           "ko": "메시지가 없습니다.", "kind": "ui", "module": "portal"},
    {"key": "admin_users_title",             "ru": "Пользователи",                                        "en": "Users",                                      "ko": "사용자", "kind": "ui", "module": "portal"},
    {"key": "admin_user_detail_title",       "ru": "Пользователь",                                        "en": "User",                                       "ko": "사용자", "kind": "ui", "module": "portal"},
    {"key": "admin_settings_title",          "ru": "Настройки сервера",                                   "en": "Server settings",                            "ko": "서버 설정", "kind": "ui", "module": "portal"},
    {"key": "admin_col_login",               "ru": "Логин",                                               "en": "Username",                                   "ko": "아이디", "kind": "ui", "module": "portal"},
    {"key": "admin_col_email",               "ru": "Email",                                               "en": "Email",                                      "ko": "이메일", "kind": "ui", "module": "portal"},
    {"key": "admin_col_roles",               "ru": "Роли",                                                "en": "Roles",                                      "ko": "역할", "kind": "ui", "module": "portal"},
    {"key": "admin_col_actions",             "ru": "Действия",                                            "en": "Actions",                                    "ko": "작업", "kind": "ui", "module": "portal"},
    {"key": "admin_action_view",             "ru": "Открыть",                                             "en": "View",                                       "ko": "보기", "kind": "ui", "module": "portal"},
    {"key": "admin_action_reset_password",   "ru": "Сбросить пароль",                                     "en": "Reset password",                             "ko": "비밀번호 재설정", "kind": "ui", "module": "portal"},
    {"key": "admin_action_wipe_data",        "ru": "Удалить данные модулей",                              "en": "Wipe module data",                           "ko": "모듈 데이터 삭제", "kind": "ui", "module": "portal"},
    {"key": "admin_action_export",           "ru": "Экспортировать данные",                               "en": "Export data",                                "ko": "데이터 낸본내기", "kind": "ui", "module": "portal"},
    {"key": "admin_action_transfer",         "ru": "Перенести данные",                                    "en": "Transfer data",                              "ko": "데이터 이전", "kind": "ui", "module": "portal"},
    {"key": "admin_action_copy",             "ru": "Копировать таблицы",                                  "en": "Copy tables",                                "ko": "테이블 복사", "kind": "ui", "module": "portal"},
    {"key": "admin_btn_save",                "ru": "Сохранить",                                           "en": "Save",                                       "ko": "저장", "kind": "ui", "module": "portal"},
    {"key": "admin_btn_search",              "ru": "Поиск",                                               "en": "Search",                                     "ko": "검색", "kind": "ui", "module": "portal"},
    {"key": "admin_btn_test_email",          "ru": "Отправить тестовое письмо",                           "en": "Send test email",                            "ko": "테스트 이메일 본내기", "kind": "ui", "module": "portal"},
    {"key": "admin_role_user",               "ru": "Пользователь",                                        "en": "User",                                       "ko": "사용자", "kind": "ui", "module": "portal"},
    {"key": "admin_role_admin",              "ru": "Администратор",                                       "en": "Admin",                                      "ko": "관리자", "kind": "ui", "module": "portal"},
    {"key": "admin_role_owner",              "ru": "Владелец",                                            "en": "Owner",                                      "ko": "소유자", "kind": "ui", "module": "portal"},
    {"key": "admin_role_user_desc",          "ru": "Может пользоваться личным кабинетом, финансами и видеть свои данные.", "en": "Can use the personal profile, finances and view own data.", "ko": "개인 프로필, 재정 기능을 사용하고 자신의 데이터를 볼 수 있습니다.", "kind": "ui", "module": "portal"},
    {"key": "admin_role_admin_desc",         "ru": "Управляет пользователями и серверными настройками, включая SMTP.", "en": "Manages users and server settings, including SMTP.", "ko": "사용자와 SMTP를 포함한 서버 설정을 관리합니다.", "kind": "ui", "module": "portal"},
    {"key": "admin_role_owner_desc",         "ru": "Полный доступ ко всем функциям и настройкам платформы.", "en": "Full access to all platform features and settings.", "ko": "플랫폼의 모든 기능과 설정에 대한 전체 접근 권한.", "kind": "ui", "module": "portal"},
    {"key": "admin_smtp_host",               "ru": "SMTP сервер",                                         "en": "SMTP host",                                  "ko": "SMTP 호스트", "kind": "ui", "module": "portal"},
    {"key": "admin_smtp_port",               "ru": "SMTP порт",                                           "en": "SMTP port",                                  "ko": "SMTP 포트", "kind": "ui", "module": "portal"},
    {"key": "admin_smtp_user",               "ru": "SMTP пользователь",                                   "en": "SMTP user",                                  "ko": "SMTP 사용자", "kind": "ui", "module": "portal"},
    {"key": "admin_smtp_password",           "ru": "SMTP пароль",                                         "en": "SMTP password",                              "ko": "SMTP 비밀번호", "kind": "ui", "module": "portal"},
    {"key": "admin_smtp_use_tls",            "ru": "Использовать TLS",                                    "en": "Use TLS",                                    "ko": "TLS 사용", "kind": "ui", "module": "portal"},
    {"key": "admin_mail_from",               "ru": "Email отправителя",                                   "en": "From email",                                 "ko": "본내는 이메일", "kind": "ui", "module": "portal"},
    {"key": "admin_mail_from_name",          "ru": "Имя отправителя",                                     "en": "From name",                                  "ko": "본내는 사람", "kind": "ui", "module": "portal"},
    {"key": "admin_alert_confirm_wipe",      "ru": "Удалить все данные пользователя во всех модулях? Это необратимо.",
                                                       "en": "Delete all user data in every module? This cannot be undone.",
                                                       "ko": "모든 모듈의 사용자 데이터를 삭제하시겠습니까? 되돌릴 수 없습니다.", "kind": "ui", "module": "portal"},
    {"key": "admin_alert_confirm_reset",     "ru": "Сгенерировать ссылку для сброса пароля и временный пароль?",
                                                       "en": "Generate a password reset link and temporary password?",
                                                       "ko": "비밀번호 재설정 링크와 임시 비밀번호를 생성하시겠습니까?", "kind": "ui", "module": "portal"},
    {"key": "admin_saved",                   "ru": "Сохранено",                                           "en": "Saved",                                      "ko": "저장되었습니다", "kind": "ui", "module": "portal"},
    {"key": "admin_save_failed",             "ru": "Не удалось сохранить",                                "en": "Save failed",                                "ko": "저장 실패", "kind": "ui", "module": "portal"},
    {"key": "admin_action_failed",           "ru": "Операция не удалась",                                 "en": "Action failed",                              "ko": "작업 실패", "kind": "ui", "module": "portal"},
    {"key": "admin_rows_deleted",            "ru": "строк удалено",                                       "en": "rows deleted",                               "ko": "행 삭제됨", "kind": "ui", "module": "portal"},
    {"key": "admin_search_placeholder",      "ru": "Поиск по логину или email...",                        "en": "Search by username or email...",             "ko": "아이디 또는 이메일 검색...", "kind": "ui", "module": "portal"},
    {"key": "admin_stats_title",             "ru": "Статистика",                                          "en": "Statistics",                                 "ko": "통계", "kind": "ui", "module": "portal"},
    {"key": "admin_stat_users",              "ru": "Пользователей",                                       "en": "Users",                                      "ko": "사용자", "kind": "ui", "module": "portal"},
    {"key": "admin_stat_admins",             "ru": "Администраторов",                                     "en": "Admins",                                     "ko": "관리자", "kind": "ui", "module": "portal"},
    {"key": "admin_stat_money_rows",         "ru": "Строк финансов",                                      "en": "Finance rows",                               "ko": "재정 행", "kind": "ui", "module": "portal"},
    {"key": "admin_dashboard_welcome",       "ru": "Центральная панель управления платформой Avalone.",   "en": "Central management panel for the Avalone platform.",
                                                       "ko": "Avalone 플랫폼 중앙 관리 패널입니다.", "kind": "ui", "module": "portal"},
    {"key": "admin_section_edit",            "ru": "Редактирование",                                      "en": "Edit",                                       "ko": "편집", "kind": "ui", "module": "portal"},
    {"key": "admin_section_actions",         "ru": "Действия",                                            "en": "Actions",                                    "ko": "작업", "kind": "ui", "module": "portal"},
    {"key": "admin_settings_smtp",           "ru": "Настройки SMTP",                                      "en": "SMTP settings",                              "ko": "SMTP 설정", "kind": "ui", "module": "portal"},
    {"key": "admin_settings_test_email",     "ru": "Тестовое письмо",                                     "en": "Test email",                                 "ko": "테스트 이메일", "kind": "ui", "module": "portal"},
    {"key": "admin_test_email_to",           "ru": "Кому",                                                "en": "To",                                         "ko": "받는 사람", "kind": "ui", "module": "portal"},
    {"key": "admin_test_email_sent",         "ru": "Тестовое письмо отправлено.",                         "en": "Test email sent.",                           "ko": "테스트 이메일을 본냈습니다.", "kind": "ui", "module": "portal"},
    {"key": "admin_test_email_failed",       "ru": "Не удалось отправить тестовое письмо.",               "en": "Failed to send test email.",                 "ko": "테스트 이메일 본내기 실패.", "kind": "ui", "module": "portal"},

    # Referral / share
    {"key": "toast_share_link_copied",       "ru": "Ссылка скопирована",                                  "en": "Link copied",                                "ko": "링크가 복사되었습니다", "kind": "ui", "module": "portal"},
    {"key": "referral_title",                "ru": "Пригласить друзей",                                   "en": "Invite friends",                             "ko": "친구 초대", "kind": "ui", "module": "portal"},
    {"key": "referral_code_label",           "ru": "Ваш код",                                             "en": "Your code",                                  "ko": "내 코드", "kind": "ui", "module": "portal"},
    {"key": "referral_invitees_label",       "ru": "Приглашённые",                                        "en": "Invitees",                                   "ko": "초대한 사람", "kind": "ui", "module": "portal"},
    {"key": "referral_empty",                "ru": "Пока никто не воспользовался вашей ссылкой.",         "en": "No one has used your link yet.",             "ko": "아직 링크를 사용한 사람이 없습니다.", "kind": "ui", "module": "portal"},
    {"key": "referral_share_hint",           "ru": "Поделитесь ссылкой — друзья получат доступ к Avalone.", "en": "Share the link — friends get access to Avalone.", "ko": "링크를 공유하면 친구들이 Avalone을 사용할 수 있습니다.", "kind": "ui", "module": "portal"},

    # Screen time
    {"key": "screen_time_title",             "ru": "Время в приложении",                                  "en": "Screen time",                                "ko": "사용 시간", "kind": "ui", "module": "portal"},
    {"key": "screen_time_today",             "ru": "Сегодня",                                             "en": "Today",                                      "ko": "오늘", "kind": "ui", "module": "portal"},
    {"key": "screen_time_total",             "ru": "Всего",                                               "en": "Total",                                      "ko": "전체", "kind": "ui", "module": "portal"},

    # Phase 2: share dialog strings.
    {"key": "share_copy_prompt",             "ru": "Скопируйте ссылку:",                                  "en": "Copy link:",                                 "ko": "링크를 복사하세요:", "kind": "ui", "module": "portal"},

    # Phase 2: profile referral / screen time.
    {"key": "profile_referral_title",        "ru": "Пригласить друзей",                                   "en": "Invite friends",                             "ko": "친구 초대", "kind": "ui", "module": "portal"},
    {"key": "profile_referral_code_label",   "ru": "Ваш код",                                             "en": "Your code",                                  "ko": "내 코드", "kind": "ui", "module": "portal"},
    {"key": "profile_referral_invitees",     "ru": "Приглашённые",                                        "en": "Invitees",                                   "ko": "초대한 사람", "kind": "ui", "module": "portal"},
    {"key": "profile_referral_empty",        "ru": "Пока никто не воспользовался вашей ссылкой.",         "en": "No one has used your link yet.",             "ko": "아직 링크를 사용한 사람이 없습니다.", "kind": "ui", "module": "portal"},
    {"key": "profile_referral_share_hint",   "ru": "Поделитесь ссылкой — друзья получат доступ к Avalone.", "en": "Share the link — friends get access to Avalone.", "ko": "링크를 공유하면 친구들이 Avalone을 사용할 수 있습니다.", "kind": "ui", "module": "portal"},
    {"key": "profile_referral_copy",         "ru": "Копировать",                                          "en": "Copy",                                       "ko": "복사", "kind": "ui", "module": "portal"},
    {"key": "profile_screen_time_title",     "ru": "Время в приложении",                                  "en": "Screen time",                                "ko": "사용 시간", "kind": "ui", "module": "portal"},
    {"key": "profile_screen_time_today",     "ru": "Сегодня",                                             "en": "Today",                                      "ko": "오늘", "kind": "ui", "module": "portal"},
    {"key": "profile_screen_time_total",     "ru": "Всего",                                               "en": "Total",                                      "ko": "전체", "kind": "ui", "module": "portal"},

    # Phase 2: public landing page.
    {"key": "landing_sign_up_title",         "ru": "Создать аккаунт",                                     "en": "Create account",                             "ko": "계정 만들기", "kind": "ui", "module": "portal"},
    {"key": "landing_sign_up_text",          "ru": "Присоединяйтесь к Avalone — все инструменты под рукой.", "en": "Join Avalone — all your tools in one place.", "ko": "Avalone에 가입하세요 — 모든 도구가 한 곳에 있습니다.", "kind": "ui", "module": "portal"},
    {"key": "landing_btn_register",          "ru": "Зарегистрироваться",                                  "en": "Sign up",                                    "ko": "회원가입", "kind": "ui", "module": "portal"},
    {"key": "landing_btn_login",             "ru": "Войти",                                               "en": "Sign in",                                  "ko": "로그인", "kind": "ui", "module": "portal"},

    # Work module
    {"key": "app_work",                      "ru": "Работа",                                              "en": "Work",                                       "ko": "일자리", "kind": "ui", "module": "portal"},
    {"key": "app_work_desc",                 "ru": "Вакансии и подработки в Южной Корее.",                "en": "Jobs and part-time work in South Korea.",    "ko": "대한민국의 구인 및 아를바이트.", "kind": "ui", "module": "portal"},
    {"key": "work_page_title",               "ru": "Вакансии",                                            "en": "Job postings",                               "ko": "채용 공고", "kind": "ui", "module": "portal"},
    {"key": "work_no_jobs",                  "ru": "Пока нет объявлений. Нажмите «Обновить», чтобы загрузить.", "en": "No postings yet. Tap Refresh to load.",      "ko": "공고가 없습니다. 새로고침을 눌러주세요.", "kind": "ui", "module": "portal"},
    {"key": "work_refresh",                  "ru": "Обновить",                                            "en": "Refresh",                                    "ko": "새로고침", "kind": "ui", "module": "portal"},
    {"key": "work_refreshing",               "ru": "Загрузка...",                                         "en": "Loading...",                                 "ko": "로딩 중...", "kind": "ui", "module": "portal"},
    {"key": "work_source_label",             "ru": "Источник",                                            "en": "Source",                                     "ko": "출처", "kind": "ui", "module": "portal"},
    {"key": "work_posted_at",                "ru": "Опубликовано",                                        "en": "Posted",                                     "ko": "게시일", "kind": "ui", "module": "portal"},
    {"key": "work_employer",                 "ru": "Работодатель",                                        "en": "Employer",                                   "ko": "고용주", "kind": "ui", "module": "portal"},
    {"key": "work_contact_phone",            "ru": "Телефон",                                             "en": "Phone",                                      "ko": "전화", "kind": "ui", "module": "portal"},
    {"key": "work_contact_email",            "ru": "Email",                                               "en": "Email",                                      "ko": "이메일", "kind": "ui", "module": "portal"},
    {"key": "work_visa_type",                "ru": "Виза",                                                "en": "Visa",                                       "ko": "비자", "kind": "ui", "module": "portal"},
    {"key": "work_location",                 "ru": "Локация",                                             "en": "Location",                                   "ko": "지역", "kind": "ui", "module": "portal"},
    {"key": "work_job_type",                 "ru": "Тип работы",                                          "en": "Job type",                                   "ko": "직종", "kind": "ui", "module": "portal"},
    {"key": "work_original_link",            "ru": "Открыть оригинал",                                    "en": "Open original",                              "ko": "원문 보기", "kind": "ui", "module": "portal"},
    {"key": "work_disclaimer",               "ru": "Объявления собраны из открытых источников с целью перевода и помощи неносителям корейского/английского языка. Права на оригинальные тексты принадлежат их авторам.", "en": "Postings are collected from public sources for translation and to help non-Korean/English speakers. Original texts belong to their respective authors.", "ko": "공개된 출처에서 수집된 공고는 번역 및 한국어/영어 비원어민 지원을 위해 제공됩니다. 원문의 권리는 해당 저작자에게 있습니다.", "kind": "ui", "module": "portal"},
    {"key": "work_filter_location",          "ru": "Локация",                                             "en": "Location",                                   "ko": "지역", "kind": "ui", "module": "portal"},
    {"key": "work_location_lang",            "ru": "Язык",                                                "en": "Language",                                   "ko": "언어", "kind": "ui", "module": "portal"},
    {"key": "work_filter_source",            "ru": "Источник",                                            "en": "Source",                                     "ko": "출처", "kind": "ui", "module": "portal"},
    {"key": "work_filter_period",            "ru": "Период",                                              "en": "Period",                                     "ko": "기간", "kind": "ui", "module": "portal"},
    {"key": "work_filter_all",               "ru": "Все",                                                 "en": "All",                                        "ko": "전체", "kind": "ui", "module": "portal"},
    {"key": "work_filter_all_time",          "ru": "За всё время",                                        "en": "All time",                                   "ko": "전체 기간", "kind": "ui", "module": "portal"},
    {"key": "work_days",                     "ru": "дн.",                                                 "en": "days",                                       "ko": "일", "kind": "ui", "module": "portal"},
    {"key": "work_show_original",            "ru": "Оригинал",                                            "en": "Original",                                   "ko": "원문", "kind": "ui", "module": "portal"},
    {"key": "work_show_translation",         "ru": "Перевод",                                             "en": "Translation",                                "ko": "번역", "kind": "ui", "module": "portal"},
    {"key": "work_filter_search",            "ru": "Поиск",                                               "en": "Search",                                     "ko": "검색", "kind": "ui", "module": "portal"},
    {"key": "work_filter_visa",              "ru": "Виза",                                                "en": "Visa",                                       "ko": "비자", "kind": "ui", "module": "portal"},
    {"key": "work_filter_job_type",          "ru": "Тип работы",                                          "en": "Job type",                                   "ko": "직종", "kind": "ui", "module": "portal"},
    {"key": "work_filter_country",           "ru": "Страна",                                              "en": "Country",                                    "ko": "국가", "kind": "ui", "module": "portal"},
    {"key": "work_salary",                   "ru": "Зарплата",                                            "en": "Salary",                                     "ko": "급여", "kind": "ui", "module": "portal"},
    {"key": "work_pay_type",                 "ru": "Тип оплаты",                                          "en": "Pay type",                                   "ko": "지급유형", "kind": "ui", "module": "portal"},
    {"key": "work_today",                    "ru": "сегодня",                                             "en": "today",                                      "ko": "오늘", "kind": "ui", "module": "portal"},
    {"key": "work_yesterday",                "ru": "вчера",                                               "en": "yesterday",                                  "ko": "어제", "kind": "ui", "module": "portal"},
    {"key": "work_days_ago",                 "ru": "дн. назад",                                           "en": "days ago",                                   "ko": "일 전", "kind": "ui", "module": "portal"},
    {"key": "work_days_left",                "ru": "дн. до дедлайна",                                     "en": "days left",                                  "ko": "일 남음", "kind": "ui", "module": "portal"},
    {"key": "work_new_badge",                "ru": "Новое",                                               "en": "New",                                        "ko": "신규", "kind": "ui", "module": "portal"},
    {"key": "work_total_jobs",               "ru": "Всего вакансий",                                      "en": "Total jobs",                                 "ko": "총 채용 공고", "kind": "ui", "module": "portal"},
    {"key": "work_page_of",                  "ru": "из",                                                  "en": "of",                                         "ko": "중", "kind": "ui", "module": "portal"},
    {"key": "work_prev",                     "ru": "Назад",                                               "en": "Previous",                                   "ko": "이전", "kind": "ui", "module": "portal"},
    {"key": "work_next",                     "ru": "Вперёд",                                              "en": "Next",                                       "ko": "다음", "kind": "ui", "module": "portal"},
    {"key": "work_filter_apply",             "ru": "Показать",                                            "en": "Show",                                       "ko": "보기", "kind": "ui", "module": "portal"},
    {"key": "work_filter_reset",             "ru": "Сбросить",                                            "en": "Reset",                                      "ko": "초기화", "kind": "ui", "module": "portal"},
    {"key": "work_new_posts_banner",         "ru": "Появились новые объявления",                          "en": "New postings available",                     "ko": "새 공고가 있습니다", "kind": "ui", "module": "portal"},
    {"key": "work_new_posts_reload",         "ru": "Обновить ленту",                                      "en": "Refresh feed",                               "ko": "피드 새로고침", "kind": "ui", "module": "portal"},
    {"key": "work_tab_feed",                 "ru": "Лента",                                               "en": "Feed",                                       "ko": "피드", "kind": "ui", "module": "portal"},
    {"key": "work_tab_saved",                "ru": "Сохранённые",                                         "en": "Saved",                                      "ko": "저장", "kind": "ui", "module": "portal"},
    {"key": "work_tab_hidden",               "ru": "Скрытые",                                             "en": "Hidden",                                     "ko": "숨김", "kind": "ui", "module": "portal"},
    {"key": "work_saved_page_title",         "ru": "Сохранённые вакансии",                                "en": "Saved job postings",                         "ko": "저장한 채용 공고", "kind": "ui", "module": "portal"},
    {"key": "work_hidden_page_title",        "ru": "Скрытые вакансии",                                    "en": "Hidden job postings",                        "ko": "숨긴 채용 공고", "kind": "ui", "module": "portal"},
    {"key": "work_filter_saved_only",        "ru": "Только сохранённые",                                  "en": "Saved only",                                 "ko": "저장만", "kind": "ui", "module": "portal"},
    {"key": "work_filter_show_hidden",       "ru": "Показывать скрытые",                                  "en": "Show hidden",                                "ko": "숨김 표시", "kind": "ui", "module": "portal"},
    {"key": "work_filter_reset_view",        "ru": "Сбросить фильтр",                                     "en": "Reset filter",                               "ko": "필터 초기화", "kind": "ui", "module": "portal"},
    {"key": "work_select_all",               "ru": "Выбрать все",                                         "en": "Select all",                                 "ko": "모두 선택", "kind": "ui", "module": "portal"},
    {"key": "work_select_job",               "ru": "Выбрать объявление",                                  "en": "Select posting",                             "ko": "공고 선택", "kind": "ui", "module": "portal"},
    {"key": "work_selected",                 "ru": "выбрано",                                             "en": "selected",                                   "ko": "선택됨", "kind": "ui", "module": "portal"},
    {"key": "work_bulk_actions",             "ru": "Массовые действия",                                   "en": "Bulk actions",                               "ko": "일괄 작업", "kind": "ui", "module": "portal"},
    {"key": "work_action_hide",              "ru": "Скрыть",                                              "en": "Hide",                                       "ko": "숨기기", "kind": "ui", "module": "portal"},
    {"key": "work_action_show",              "ru": "Показать",                                            "en": "Show",                                       "ko": "표시", "kind": "ui", "module": "portal"},
    {"key": "work_action_bookmark",          "ru": "В избранное",                                         "en": "Bookmark",                                   "ko": "북마크", "kind": "ui", "module": "portal"},
    {"key": "work_action_like",              "ru": "Нравится",                                            "en": "Like",                                       "ko": "좋아요", "kind": "ui", "module": "portal"},
    {"key": "work_action_unbookmark",        "ru": "Убрать из избранного",                                "en": "Remove bookmark",                            "ko": "북마크 해제", "kind": "ui", "module": "portal"},
    {"key": "work_action_unlike",            "ru": "Убрать лайк",                                         "en": "Unlike",                                     "ko": "좋아요 취소", "kind": "ui", "module": "portal"},
    {"key": "work_login_to_act",             "ru": "Войдите, чтобы выполнить действие",                   "en": "Sign in to perform this action",             "ko": "작업을 수행하려면 로그인하세요", "kind": "ui", "module": "portal"},
    {"key": "work_toast_ok",                 "ru": "Готово",                                              "en": "Done",                                       "ko": "완료", "kind": "ui", "module": "portal"},
    {"key": "work_toast_err",                "ru": "Не удалось. Попробуйте ещё раз.",                    "en": "Failed. Please try again.",                  "ko": "실패했습니다. 다시 시도해주세요.", "kind": "ui", "module": "portal"},
    {"key": "work_show_filters",             "ru": "Показать фильтры",                                    "en": "Show filters",                               "ko": "필터 표시", "kind": "ui", "module": "portal"},
    {"key": "work_hide_filters",             "ru": "Скрыть фильтры",                                      "en": "Hide filters",                               "ko": "필터 숨기기", "kind": "ui", "module": "portal"},
    {"key": "work_collapse_controls",        "ru": "Свернуть панель",                                     "en": "Collapse panel",                             "ko": "패널 접기", "kind": "ui", "module": "portal"},
    {"key": "work_expand_controls",          "ru": "Развернуть панель",                                   "en": "Expand panel",                               "ko": "패널 펼치기", "kind": "ui", "module": "portal"},
    {"key": "work_site_114114_co_kr",        "ru": "114114구인구직",                                      "en": "114114 Jobs",                                "ko": "114114구인구직", "kind": "ui", "module": "portal"},
    {"key": "work_site_albamon_com",         "ru": "Albamon",                                             "en": "Albamon",                                    "ko": "알바몬", "kind": "ui", "module": "portal"},
    {"key": "work_site_jobkorea_co_kr",      "ru": "JobKorea",                                            "en": "JobKorea",                                   "ko": "잡코리아", "kind": "ui", "module": "portal"},
    {"key": "work_site_koreabridge_net",     "ru": "Koreabridge",                                         "en": "Koreabridge",                                "ko": "코리아브리지", "kind": "ui", "module": "portal"},
    {"key": "work_site_saramin_co_kr",       "ru": "Saramin",                                             "en": "Saramin",                                    "ko": "사람인", "kind": "ui", "module": "portal"},
    {"key": "work_country_kr",               "ru": "Южная Корея",                                         "en": "South Korea",                                "ko": "대한민국", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_fulltime",         "ru": "Полная занятость",                                    "en": "Full-time",                                  "ko": "정규직", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_parttime",         "ru": "Частичная занятость",                                 "en": "Part-time",                                  "ko": "파트타임", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_contract",         "ru": "Контракт",                                            "en": "Contract",                                   "ko": "계약직", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_internship",       "ru": "Стажировка",                                          "en": "Internship",                                 "ko": "인턴", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_freelance",        "ru": "Фриланс",                                             "en": "Freelance",                                  "ko": "프리랜서", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_daily_temp",       "ru": "Подработка / временная",                              "en": "Daily / temp",                               "ko": "일당/임시", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_daily_pay",        "ru": "Ежедневная оплата",                                   "en": "Daily pay",                                  "ko": "일당 지급", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_fulltime_monthly", "ru": "Полная занятость / помесячно",                        "en": "Full-time / monthly",                        "ko": "정규직 / 월급", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_fulltime_yearly",  "ru": "Полная занятость / погодово",                         "en": "Full-time / yearly",                         "ko": "정규직 / 연봉", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_계약직_후_정규직전환", "ru": "Контракт с переходом на постоянную",                  "en": "Contract-to-hire",                           "ko": "계약직 후 정규직전환", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_상용직",           "ru": "Постоянная работа",                                   "en": "Permanent",                                  "ko": "상용직", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_위촉직",           "ru": "По договору поручения",                               "en": "Commissioned",                               "ko": "위촉직", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_임시직",           "ru": "Временная работа",                                    "en": "Temporary",                                  "ko": "임시직", "kind": "ui", "module": "portal"},
    {"key": "work_jobtype_parttime_hourly",  "ru": "Частичная занятость / почасовая",                     "en": "Part-time / hourly",                         "ko": "파트타임 / 시급", "kind": "ui", "module": "portal"},
    {"key": "work_visa_e2",                  "ru": "E-2",                                                 "en": "E-2",                                        "ko": "E-2", "kind": "ui", "module": "portal"},
    {"key": "work_visa_f2",                  "ru": "F-2",                                                 "en": "F-2",                                        "ko": "F-2", "kind": "ui", "module": "portal"},
    {"key": "work_visa_f4",                  "ru": "F-4",                                                 "en": "F-4",                                        "ko": "F-4", "kind": "ui", "module": "portal"},
    {"key": "work_visa_f5",                  "ru": "F-5",                                                 "en": "F-5",                                        "ko": "F-5", "kind": "ui", "module": "portal"},
    {"key": "work_visa_f6",                  "ru": "F-6",                                                 "en": "F-6",                                        "ko": "F-6", "kind": "ui", "module": "portal"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

_repo: "GlossaryRepository" | None = None


def _get_repo() -> "GlossaryRepository":
    global _repo
    if _repo is None:
        from avalone_core.glossary_service import GlossaryRepository
        _repo = GlossaryRepository()
    return _repo


def ensure_schema() -> None:
    return _get_repo().ensure_schema()


def upsert(key: str, ru: str = "", en: str = "", ko: str = "", kind: str = "ui",
           module: str = "", desc: str | None = None) -> None:
    return _get_repo().upsert(key, ru, en, ko, kind, module, desc)


def upsert_many(rows: list[dict[str, Any]]) -> int:
    return _get_repo().upsert_many(rows)


def set_desc(key: str, desc: str) -> None:
    return _get_repo().set_desc(key, desc)


def touch(key: str) -> None:
    return _get_repo().touch(key)


def get(key: str, lang: str = "ru") -> str:
    return _get_repo().get(key, lang)


# Alias used in templates and registry.
t = get


def td(value: str, prefix: str, lang: str = "ru") -> str:
    """Translate a dynamic value through the glossary.

    Builds a key ``{prefix}_{sanitized_value}`` and returns the glossary
    translation if it exists; otherwise returns the original value unchanged.
    This lets dropdowns, badges and tags use glossary translations without
    having to hardcode every possible raw value.
    """
    if not value:
        return value
    raw = str(value).strip()
    safe = raw.lower().replace("-", "")
    for ch in " /.()[],:\"":
        safe = safe.replace(ch, "_")
    while "__" in safe:
        safe = safe.replace("__", "_")
    safe = safe.strip("_")
    key = f"{prefix}_{safe}"
    translated = _get_repo().get(key, lang)
    return translated if translated != key else raw


def td_list(value: str, prefix: str, lang: str = "ru", sep: str = ",") -> str:
    """Translate a comma-separated list of dynamic values.

    Each item is trimmed and translated via :func:`td`; unknown items are kept
    as-is.  Useful for visa type combinations like ``"F-2, F-4, F-5"``.
    """
    if not value:
        return value
    parts = [part.strip() for part in str(value).split(sep)]
    translated = [td(part, prefix, lang) for part in parts if part]
    return ", ".join(translated)


def all_by_lang(kind: str | None = None, module: str | None = None) -> dict[str, dict[str, str]]:
    return _get_repo().all_by_lang(kind, module)


def i18n_js() -> dict[str, dict[str, str]]:
    return _get_repo().i18n_js()


def entries(kind: str | None = None, module: str | None = None) -> list[dict[str, Any]]:
    return _get_repo().entries(kind, module)


def describe(key: str) -> str:
    return _get_repo().describe(key)


def missing_desc(kind: str | None = None, module: str | None = None) -> list[str]:
    return _get_repo().missing_desc(kind, module)


def count(kind: str | None = None, module: str | None = None) -> int:
    return _get_repo().count(kind, module)


def migrate_legacy() -> dict[str, int]:
    return _get_repo().migrate_legacy()


def seed_portal() -> int:
    return _get_repo().seed_portal()


def apply_descriptions() -> int:
    return _get_repo().apply_descriptions()


def migrate() -> dict[str, Any]:
    return _get_repo().migrate()


def audit() -> dict[str, Any]:
    return _get_repo().audit()


def __getattr__(name: str) -> Any:
    if name == "SCHEMA":
        from avalone_core.glossary_service import SCHEMA
        return SCHEMA
    if name == "GlossaryRepository":
        from avalone_core.glossary_service import GlossaryRepository
        return GlossaryRepository
    if name == "GlossaryService":
        from avalone_core.glossary_service import GlossaryService
        return GlossaryService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
