"""Meta-descriptions for every glossary key.

The goal: any key, even without a hand-written description, carries enough
context for an AI/human translator to produce a correct translation.

Rules are applied EXACT -> PREFIX -> GENERIC. Domain-specific prefixes
(currencies, categories, tips) are described explicitly so that generic
finance/work vocabulary does not end up ambiguous.
"""

from typing import Any

EXACT: dict[str, str] = {
    # Finance/work form fields where the prefix alone is not enough.
    "f_money_from":         "Form field label: which account the money was paid FROM (expense source).",
    "f_money_to_in":        "Form field label: which account the money came IN to (income destination).",
    "f_money_from_transfer":"Form field label: source account in a transfer between the user's own accounts.",
    "f_income_src":         "Form field label: the income source (where incoming money comes from).",
    "f_category":           "Form field label for picking an expense category (what money is spent on).",
    "f_occurred_toggle":    "Toggle label to set when the transaction actually happened, vs when it was recorded.",

    # Operation types.
    "op_expense":           "Transaction type option: spending money (an expense).",
    "op_income":            "Transaction type option: receiving money (income).",
    "op_transfer":          "Transaction type option: moving money between the user's own accounts.",

    # Finance edit/manage hub.
    "edit_journal":         "Menu item: edit the journal / list of recorded transactions.",
    "edit_accounts":        "Menu item: edit the user's money accounts (cash, bank, cards).",
    "edit_categories":      "Menu item: edit expense categories.",
    "edit_incomes":         "Menu item: edit income sources.",

    # Navigation / tabs.
    "tab_entry":            "Bottom navigation tab: home / new transaction entry. Shown as a house icon.",
    "trash_restore":        "Button to restore (un-hide / un-cancel) a previously hidden or cancelled item.",
    "flt_hide_cancelled":   "Checkbox to hide cancelled transactions from the journal list.",

    # First-run wizard (finance).
    "wz3_b":                "First-run wizard step: instruction to record current real balances (cash in various currencies, cards, credit card) as 'income' operations so balances reflect reality. Keep it concrete and encouraging.",
    "wz4_b":                "First-run wizard step explaining DEBT modeling: create an account for money borrowed from someone, do NOT fund it, just record an expense from it so the balance goes negative — the negative balance IS the debt; repaying funds it back to zero. Translate the concept clearly, the example name is illustrative.",

    # Work/rides specific.
    "work_trip_driver":     "Role label: the user is driving and offering seats.",
    "work_trip_passenger":  "Role label: the user is a passenger in someone else's trip.",
    "work_trip_not_going":  "Status label: the user is not joining the trip.",

    # Portal admin role labels.
    "admin_role_user":            "Admin panel badge/label for the baseline 'user' RBAC role.",
    "admin_role_finance_manager": "Admin panel badge/label for the 'finance_manager' RBAC role.",
    "admin_role_admin":           "Admin panel badge/label for the 'admin' RBAC role.",
    "admin_role_owner":           "Admin panel badge/label for the 'owner' RBAC role.",

    # Portal brand / shared shell.
    "brand":                "Product brand name. Keep as 'Avalone' unless the target script requires transliteration.",
    "brand_tagline":        "Marketing tagline shown under the logo: short phrase describing Avalone as a unified toolset.",
    "portal_title":         "Page title for the Avalone portal landing page.",
    "status_text":          "Short paragraph on the portal home explaining that Work and Finance are live and what the user can do.",
    "coming_soon":          "Prefix text before a planned module name, e.g. 'Planned: Education'.",
    "search_placeholder":   "Placeholder text in the global search input.",
    "footer":               "Footer copyright/brand line on the portal.",

    # Auth pages (portal).
    "auth_login_title":     "Page title and heading for the login screen.",
    "auth_register_title":  "Page title and heading for the registration screen.",
    "auth_profile_title":   "Page title and heading for the user profile screen.",
    "auth_label_login":     "Label for the username/login input field.",
    "auth_label_password":  "Label for the password input field.",
    "auth_label_password2": "Label for the password confirmation input field.",
    "auth_label_invite":    "Label for the optional invitation code input field.",
    "auth_hint_password_min": "Hint below the password field about the minimum length.",
    "auth_btn_login":       "Submit button on the login form.",
    "auth_btn_register":    "Submit button on the registration form.",
    "auth_btn_change_password": "Submit button on the change-password form in the profile.",
    "auth_btn_logout":      "Button that ends the user session.",
    "auth_link_to_register":"Link text prompting a user without an account to register.",
    "auth_link_to_login":   "Link text prompting an existing user to log in.",
    "auth_error_invalid_credentials": "Error message shown when login or password is wrong.",
    "auth_error_required":  "Error message shown when login or password is missing.",
    "auth_error_password_mismatch": "Error message shown when password and confirmation do not match.",
    "auth_error_password_too_short": "Error message shown when the password is shorter than the minimum length.",
    "auth_error_login_taken": "Error message shown when the chosen username is already taken.",
    "profile_password_mismatch": "Error in profile: new password and its confirmation do not match.",
    "profile_current_password_wrong": "Error in profile: the current password was entered incorrectly.",
    "profile_password_changed": "Success message in profile after the password has been updated.",
    "profile_email_missing": "Fallback text shown when the user has not set an email.",
    "profile_section_security": "Section heading for the password-change form in the profile.",
    "profile_section_session": "Section heading for the logout button in the profile.",

    # Password reset.
    "reset_forgot_title": "Page title and heading for the forgot-password screen.",
    "reset_forgot_hint": "Short explanation on the forgot-password screen.",
    "reset_label_login_or_email": "Label for the input that accepts username or email on the forgot-password form.",
    "reset_placeholder_login_or_email": "Placeholder for the username/email input on the forgot-password form.",
    "reset_btn_send": "Submit button on the forgot-password form.",
    "reset_email_subject": "Subject line of the password-reset email.",
    "reset_email_body": "Body of the password-reset email. Must contain {login} and {url} placeholders.",
    "reset_email_sent": "Success message shown after a reset link was emailed.",
    "reset_email_failed": "Error message shown when the email could not be sent. Contains {error} placeholder.",
    "reset_email_sent_no_email": "Message shown when the account exists but has no email address on file.",
    "reset_email_sent_generic": "Generic message shown after forgot-password submission to avoid account enumeration.",
    "reset_error_required": "Error shown when the forgot-password form is submitted empty.",
    "reset_dev_link_prefix": "Developer-only hint shown when mail is not configured and the reset link is displayed inline.",
    "reset_title": "Page title and heading for the new-password (reset) screen.",
    "reset_btn_save": "Submit button on the new-password form.",
    "reset_token_invalid": "Error shown when the reset token is missing, expired, or invalid.",
    "reset_password_success": "Success message shown on the login screen after a successful password reset.",
    "reset_forgot_link": "Link text on the login form that leads to the forgot-password page.",

    # Shared shell.
    "shell_apps_label":     "Tooltip/aria-label of the app-switcher button in the top bar.",
    "shell_search_label":   "Tooltip/aria-label of the global search button and its overlay input.",
    "shell_search_placeholder": "Placeholder inside the global search overlay.",
    "shell_search_close":   "Aria-label of the button that closes the search overlay.",
    "shell_theme_label":    "Tooltip/aria-label of the theme toggle button.",
    "shell_notifications_label": "Tooltip/aria-label of the notifications button.",
    "shell_profile_label":  "Tooltip/aria-label of the profile menu button.",
    "shell_profile_guest":  "Fallback user name shown when no one is logged in.",
    "shell_profile_profile":"Label of the 'Profile' link in the profile dropdown.",
    "shell_profile_login":  "Label of the 'Log in' link in the profile dropdown when logged out.",
    "shell_profile_logout": "Label of the 'Log out' link in the profile dropdown.",
    "shell_status_in_dev":  "Badge label for branches that are in development.",
    "shell_status_planned": "Badge label for branches that are planned but not yet available.",

    # Manifest / PWA.
    "manifest_name":        "PWA manifest: full application name including brand.",
    "manifest_short_name":  "PWA manifest: short application name shown under the icon.",
    "manifest_description": "PWA manifest: one-sentence description of the app.",
}

PREFIX: list[tuple[str, str]] = [
    # Finance / work UI (existing Counta/Routa conventions).
    ("f_",      "Label or placeholder for an input field in the transaction/trip entry form."),
    ("t_",      "Short toast/snackbar confirmation message shown briefly after an action."),
    ("e_",      "Short inline error message shown when input is invalid."),
    ("cf_",     "Text of a confirmation dialog/prompt before a destructive or important action."),
    ("pr_",     "Prompt asking the user to type a value (e.g. a new name)."),
    ("edit_",   "Label in the 'edit / manage' hub for choosing what to edit."),
    ("acc_",    "Label/button in the accounts editor (money accounts: cash, bank, cards)."),
    ("inc_",    "Label/button in the income-sources editor."),
    ("flt_",    "Label/control in the journal filter & sorting panel."),
    ("jf_",     "Journal filter quick option."),
    ("tab_",    "Bottom navigation tab label (often icon-only)."),
    ("scr_",    "Screen/page title heading."),
    ("op_",     "Transaction type option (expense / income / transfer) or operation title."),
    ("rv_",     "Word used when assembling a human-readable review line of a transaction before saving."),
    ("set_",    "Label in the Settings section."),
    ("sec_",    "Collapsible section heading in the 'More' menu."),
    ("ai_",     "Text in the AI analyst chat screen (read-only money questions)."),
    ("v_",      "Status text during voice input (speech-to-text prefill)."),
    ("kstep",   "Step label in the multi-step entry progress indicator (input → review → saved)."),
    ("per_",    "Recurrence period option (monthly / weekly / etc.)."),
    ("widget_", "Name of a home-screen widget (balances / journal / trips)."),
    ("notif_",  "Word in the notifications area."),
    ("wz",      "Step text in the first-run getting-started wizard: a short step title (_t) or a paragraph of instructions (_b) for a newcomer."),
    ("rep_",    "Label/title of a report or analytics view."),
    ("tip_",    "Title or body of a financial-literacy tip shown in analytics."),

    # Currency / category / catalog domain keys.
    ("cur_",    "Currency name or currency-related label."),
    ("cat_",    "Expense/income category name (e.g. food, housing, transport)."),
    ("accname_","Display name of a money account (cash, bank, card, etc.)."),

    # Portal / shared shell.
    ("app_",    "Name or description of an Avalone app/module shown in the app grid/switcher."),
    ("status_", "Status label used in the portal or shell (active / planned / in development)."),
    ("btn_",    "Label on a button or call-to-action link."),
    ("quick_",  "Label for a quick-action tile on the portal home."),
    ("nav_",    "Navigation label (top bar, bottom tab, or sidebar)."),
    ("teaser_", "Text in the 'more modules planned' teaser section on the portal."),
    ("landing_", "Text on the public portal landing page."),
    ("shell_",  "Text in the shared Avalone shell header/menu/search overlay."),
    ("auth_",   "Text in the authentication flows (login, register, profile)."),
    ("profile_","Text in the user profile screen."),
    ("manifest_", "Field in the PWA web-app manifest."),
    ("admin_",  "Label, button, or message in the platform admin dashboard."),
    ("error_",  "Error message returned by the backend or shown to the user."),

    # Phase 2: referral, screen time, devices.
    ("ref_",     "Text in the referral / invite-friends screen."),
    ("screen_",  "Text in the screen-time / usage analytics screen."),
    ("device_",  "Text in the device management screen."),
    ("share_",   "Text in the system share / invite-friends dialog."),
    ("toast_",   "Short toast/snackbar confirmation message."),
]

GENERIC = (
    "Short UI string in the Avalone platform. "
    "Translate it as an everyday app-interface term, not literally."
)


def describe(key: str) -> str:
    if key in EXACT:
        return EXACT[key]
    for pfx, d in PREFIX:
        if key.startswith(pfx):
            return d
    return GENERIC


def apply_descriptions(glossary_module: Any | None = None) -> int:
    """Apply descriptions to empty desc values in the glossary table.

    `glossary_module` is the module providing set_desc() and entries().
    Defaults to avalone_core.glossary_db.
    """
    if glossary_module is None:
        from avalone_core import glossary_db as glossary_module
    updated = 0
    for row in glossary_module.entries():
        if row.get("desc"):
            continue
        d = describe(row["key"])
        if d:
            glossary_module.set_desc(row["key"], d)
            updated += 1
    return updated
