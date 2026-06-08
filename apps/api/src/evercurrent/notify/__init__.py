"""Phase 11 notify package.

Slack DM delivery for the morning digest and urgent Card alerts.
Public surface stays small: callers reach in through the celery_tasks
wrappers or the subscriptions router. Module layout mirrors the rest of
the backend (schemas, repository, *_deliver, plus pure helpers in
quiet_hours and block_kit).
"""

from __future__ import annotations
