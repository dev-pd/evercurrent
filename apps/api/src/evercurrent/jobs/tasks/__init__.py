"""Celery task wrappers.

Each task lives in its own file and is exported from this package so the
worker module can register them by import.
"""

from evercurrent.jobs.tasks.generate_digest_for_member import generate_digest_for_member
from evercurrent.jobs.tasks.ingest_doc import ingest_document

__all__ = [
    "generate_digest_for_member",
    "ingest_document",
]
