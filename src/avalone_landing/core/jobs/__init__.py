"""Job aggregation module for the Avalone Work branch."""

from .models import JobPost
from .parser import AlbamonParser, BaseJobParser, KoreabridgeRSSParser, MultiSourceParser
from .repository import JobPostRepository
from .service import JobPostService

__all__ = [
    "BaseJobParser",
    "JobPost",
    "AlbamonParser",
    "KoreabridgeRSSParser",
    "MultiSourceParser",
    "JobPostRepository",
    "JobPostService",
]
