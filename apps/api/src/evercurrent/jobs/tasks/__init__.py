"""Celery task wrappers.

Each task lives in its own file and is exported from this package so the
worker module can register them by import.
"""

from evercurrent.jobs.tasks.generate_digests import generate_all_digests
from evercurrent.jobs.tasks.ingest_doc import ingest_document
from evercurrent.jobs.tasks.regenerate_user_digest import regenerate_user_digest

__all__ = [
    "generate_all_digests",
    "ingest_document",
    "regenerate_user_digest",
]
