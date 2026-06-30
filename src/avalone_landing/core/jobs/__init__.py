"""Job aggregation module for the Avalone Work branch."""

from .models import JobPost
from .parser import AlbamonParser, BaseJobParser, JobKoreaParser, KoreabridgeRSSParser, MultiSourceParser, SaraminParser
from .repository import JobPostRepository
from .service import JobPostService

__all__ = [
    "BaseJobParser",
    "JobPost",
    "AlbamonParser",
    "JobKoreaParser",
    "KoreabridgeRSSParser",
    "SaraminParser",
    "MultiSourceParser",
    "JobPostRepository",
    "JobPostService",
]
