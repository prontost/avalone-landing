"""Web routes for the Avalone Work branch."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from avalone_landing.core.jobs.service import JobPostService
from avalone_landing.web.dependencies import current_user, get_shell_context
from avalone_landing.web.shell_context import ShellContext

router = APIRouter(prefix="/work")


@router.get("", response_class=HTMLResponse)
async def work_index(
    request: Request,
    user=Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    """Render the job-postings feed."""
    # Lazy import avoids a circular dependency with the main app module.
    from avalone_landing.web.app import BUILD_ID, _no_cache, templates

    ctx = shell_context.build(
        templates,
        request,
        current_app="work",
        app_nav=[],
        build_id=BUILD_ID,
    )
    ctx["jobs"] = JobPostService().list_recent(limit=50)
    return _no_cache(templates.TemplateResponse(request, "work.html", ctx))


@router.post("/fetch", response_class=RedirectResponse)
async def work_fetch(request: Request):
    """Trigger a fresh fetch from the configured job board."""
    JobPostService().fetch_and_store()
    return RedirectResponse("/work", status_code=303)
