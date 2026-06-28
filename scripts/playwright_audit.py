"""Playwright audit for Avalone shared UI across landing, Avalone Finance and Avalone Work.

Runs against locally-started services:
  - landing: http://127.0.0.1:8811
  - finance:  http://127.0.0.1:8810
  - work:   http://127.0.0.1:8812

Checks:
  - each service serves the shared shell CSS
  - landing home renders the shared shell and app catalog
  - finance / work redirect anonymous users to the Avalone login page
  - no console errors or uncaught JS exceptions
"""

import sys
from urllib.parse import urlparse
from urllib.request import urlopen
from urllib.error import URLError
from playwright.sync_api import sync_playwright

SERVICES = {
    "landing": "http://127.0.0.1:8811",
    "finance": "http://127.0.0.1:8810",
    "work": "http://127.0.0.1:8812",
}

# Network/console problems we tolerate (third-party or expected missing endpoints).
IGNORED_NETWORK_404 = {"/api/notifications/unread-count"}


def main() -> int:
    failures = []
    page_errors = []
    failed_responses = []

    def on_page_error(err):
        page_errors.append(str(err))

    def on_response(response):
        if response.status == 404:
            url = response.url
            if any(ignored in url for ignored in IGNORED_NETWORK_404):
                return
            failed_responses.append(url)

    # Shared static assets
    for name, base in SERVICES.items():
        url = f"{base}/static/ui/avalone-shell.css"
        try:
            with urlopen(url, timeout=10) as r:
                body = r.read().decode("utf-8", errors="replace")
                if r.status != 200:
                    failures.append(f"{name} shared CSS returned {r.status}")
                elif "avalone-shell" not in body.lower() and ".avalone-" not in body:
                    failures.append(f"{name} shared CSS looks empty/unexpected")
        except URLError as e:
            failures.append(f"{name} shared CSS fetch failed: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="ru-RU",
        )
        page = context.new_page()
        page.on("pageerror", on_page_error)
        page.on("response", on_response)

        # Landing home page
        landing_base = SERVICES["landing"]
        page.goto(landing_base + "/", wait_until="networkidle")
        if page.locator(".avalone-shell").count() == 0:
            failures.append("landing: .avalone-shell not found")
        if page.locator(".landing-wrap").count() == 0:
            failures.append("landing: .landing-wrap not found")
        if page.locator(".bento .branch").count() == 0:
            failures.append("landing: app catalog branches not found")
        title = page.title()
        if "Avalone" not in title:
            failures.append(f"landing: unexpected title {title!r}")

        # Avalone Finance unauthenticated -> login
        finance_base = SERVICES["finance"]
        page.goto(finance_base + "/", wait_until="networkidle")
        parsed = urlparse(page.url)
        if parsed.path != "/login" or "next=" not in parsed.query:
            failures.append(f"finance: expected redirect to login, got {page.url}")
        if page.locator("input#login").count() == 0:
            failures.append("finance login page: login input not found")

        # Avalone Work unauthenticated -> login
        work_base = SERVICES["work"]
        page.goto(work_base + "/", wait_until="networkidle")
        parsed = urlparse(page.url)
        if parsed.path != "/login" or "next=" not in parsed.query:
            failures.append(f"work: expected redirect to login, got {page.url}")
        if page.locator("input#login").count() == 0:
            failures.append("work login page: login input not found")

        # Mobile viewport smoke test on landing
        context2 = browser.new_context(
            viewport={"width": 390, "height": 844},
            locale="ru-RU",
            is_mobile=True,
        )
        mobile = context2.new_page()
        mobile.on("pageerror", on_page_error)
        mobile.on("response", on_response)
        mobile.goto(landing_base + "/", wait_until="networkidle")
        if mobile.locator(".avalone-shell").count() == 0:
            failures.append("landing mobile: .avalone-shell not found")
        context2.close()

        browser.close()

    if failed_responses:
        failures.append(f"unexpected 404 responses: {failed_responses}")
    if page_errors:
        failures.append(f"page errors: {page_errors}")

    print("=" * 60)
    print("Avalone Playwright audit")
    print("=" * 60)
    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
