"""Celery background jobs.

The Celery app lives in `celery_app.celery_app`. Sync task wrappers are
in `celery_tasks.py`; each one calls `asyncio.run(<async impl>)` on
the matching coroutine in `tasks/`.
"""
