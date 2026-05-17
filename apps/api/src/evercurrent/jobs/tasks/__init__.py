"""Arq task modules.

Each task lives in its own file and is exported from this package so the
worker module can register them by import.
"""

from evercurrent.jobs.tasks.advance_day import advance_day
from evercurrent.jobs.tasks.enrich_messages import enrich_day
from evercurrent.jobs.tasks.extract_decisions import extract_decisions_for_day
from evercurrent.jobs.tasks.generate_digests import generate_all_digests
from evercurrent.jobs.tasks.ingest_doc import ingest_document
from evercurrent.jobs.tasks.refresh_today import refresh_today, synthesize_today_message
from evercurrent.jobs.tasks.regenerate_user_digest import regenerate_user_digest

__all__ = [
    "advance_day",
    "enrich_day",
    "extract_decisions_for_day",
    "generate_all_digests",
    "ingest_document",
    "refresh_today",
    "regenerate_user_digest",
    "synthesize_today_message",
]
