"""Legacy DigestRepository shim — kept for export-compat only.

The real digest persistence lives in `evercurrent.digest.repository`
under the v2 schema (project_member, day_index, card_ids, message_ids).
Callers in `api/routes/digests.py` and tasks now talk to that module.

This shim exists so `from evercurrent.db.repositories import ...` keeps
working for any caller that imports the name; it offers no methods.
"""

from __future__ import annotations


class DigestRepository:
    """Placeholder. See `evercurrent.digest.repository` for the real API."""
