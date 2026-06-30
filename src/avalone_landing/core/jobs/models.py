"""Domain model for aggregated job postings."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JobPost:
    """A job posting scraped from an external Korean job board."""

    external_guid: str
    source_site: str
    source_url: str
    title: str
    description_html: str
    description_text: str
    posted_at: datetime | None = None
    author: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    # Extracted / translated fields
    title_translated: str = ""
    description_translated: str = ""
    employer: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    visa_type: str = ""
    location: str = ""
    job_type: str = ""
    salary: str = ""
    pay_type: str = ""
