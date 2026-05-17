"""Backwards-compat shim. The Celery worker entrypoint is
``evercurrent.jobs.celery_app:celery_app``; launch with::

    celery -A evercurrent.jobs.celery_app worker --loglevel=info
    celery -A evercurrent.jobs.celery_app beat   --loglevel=info

This file used to host Arq's WorkerSettings; kept as a discoverability
hook in case downstream tooling imports it.
"""

from evercurrent.jobs.celery_app import celery_app

__all__ = ["celery_app"]
