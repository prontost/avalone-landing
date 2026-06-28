"""Class-based UI widgets for Avalone.

Every widget knows how to render itself through a Jinja2 template. Pages and
applications compose widgets instead of hardcoding HTML.
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional

from markupsafe import Markup


class Widget:
    """Base class for all UI widgets."""

    template_name: str = ""
    css_class: str = ""

    def context(self, request: Any = None) -> dict:
        """Return the template context for this widget."""
        return {"widget": self}

    def render(self, env, request: Any = None) -> Markup:
        """Render the widget to HTML using the supplied Jinja2 environment."""
        if not self.template_name:
            return Markup("")
        template = env.get_template(self.template_name)
        return Markup(template.render(self.context(request)))

    def assets(self) -> List[str]:
        """Return list of static asset URLs required by this widget."""
        return []


@dataclass
class SearchOverlay(Widget):
    template_name: str = "widgets/search_overlay.html"


@dataclass
class AppSwitcher(Widget):
    template_name: str = "widgets/app_switcher.html"
    current_app: str = "portal"
    branches: List[Any] = field(default_factory=list)


@dataclass
class ProfileMenu(Widget):
    template_name: str = "widgets/profile_menu.html"
    user: Any = None


@dataclass
class BottomNav(Widget):
    template_name: str = "widgets/bottom_nav.html"
    app_nav: List[Any] = field(default_factory=list)


@dataclass
class NavSidebar(Widget):
    template_name: str = "widgets/nav_sidebar.html"
    app_nav: List[Any] = field(default_factory=list)


@dataclass
class Shell(Widget):
    """The main application shell: header + search + app switcher + profile + nav."""

    template_name: str = "shell.html"
    current_app: str = "portal"
    user: Any = None
    sessions: List[Any] = field(default_factory=list)
    auth_modal_html: str = ""
    branches: List[Any] = field(default_factory=list)
    app_nav: List[Any] = field(default_factory=list)
    breadcrumbs: List[Any] = field(default_factory=list)
    notifications_count: int = 0
    lang: str = "ru"

    def __post_init__(self):
        def _branch_id(b):
            if isinstance(b, dict):
                return b.get("id")
            return getattr(b, "id", None)

        self.active_branch = next(
            (b for b in self.branches if _branch_id(b) == self.current_app),
            None,
        )
        if not self.active_branch:
            self.active_branch = {
                "id": "portal",
                "name": "Avalone",
                "icon": "A",
                "url": "https://avalone.online",
            }
        self.search_overlay = SearchOverlay()
        self.app_switcher = AppSwitcher(
            current_app=self.current_app, branches=self.branches
        )
        self.profile_menu = ProfileMenu(user=self.user)
        self.bottom_nav = BottomNav(app_nav=self.app_nav)
        self.nav_sidebar = NavSidebar(app_nav=self.app_nav)

    def context(self, request: Any = None) -> dict:
        return {
            "shell": self,
            "current_app": self.current_app,
            "user": self.user,
            "sessions": self.sessions,
            "auth_modal_html": self.auth_modal_html,
            "branches": self.branches,
            "app_nav": self.app_nav,
            "active_branch": self.active_branch,
            "breadcrumbs": self.breadcrumbs,
            "notifications_count": self.notifications_count,
            "search_overlay": self.search_overlay,
            "app_switcher": self.app_switcher,
            "profile_menu": self.profile_menu,
            "bottom_nav": self.bottom_nav,
            "nav_sidebar": self.nav_sidebar,
            "lang": self.lang,
        }


# ---------------------------------------------------------------------------
# Content widgets
# ---------------------------------------------------------------------------


@dataclass
class Card(Widget):
    template_name: str = "widgets/card.html"
    title: str = ""
    children: Markup = field(default_factory=lambda: Markup(""))
    extra_class: str = ""


@dataclass
class Button(Widget):
    template_name: str = "widgets/button.html"
    label: str = ""
    href: str = ""
    type: str = "button"
    variant: str = "primary"
    extra_class: str = ""


@dataclass
class PageHeader(Widget):
    template_name: str = "widgets/page_header.html"
    title: str = ""
    actions: List[Any] = field(default_factory=list)


@dataclass
class Alert(Widget):
    template_name: str = "widgets/alert.html"
    variant: str = "info"
    children: Markup = field(default_factory=lambda: Markup(""))
    extra_class: str = ""
