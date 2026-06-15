"""Expose Celery worker metrics to Prometheus.

The worker runs a prefork pool, so LLM-cost counters are incremented in
forked child processes. Prometheus' multiprocess mode has each process
write to a shared dir (PROMETHEUS_MULTIPROC_DIR); the main process serves
an aggregated /metrics on a port Prometheus scrapes."""

from __future__ import annotations

import os
from pathlib import Path

import structlog
from celery.signals import worker_init
from prometheus_client import CollectorRegistry, multiprocess, start_http_server

log = structlog.get_logger(__name__)

_PORT = 9100


@worker_init.connect
def start_worker_metrics(**_kwargs: object) -> None:
    mp_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not mp_dir:
        return
    path = Path(mp_dir)
    path.mkdir(parents=True, exist_ok=True)
    for stale in path.glob("*.db"):
        stale.unlink()
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    start_http_server(_PORT, registry=registry)
    log.info("worker.metrics.started", port=_PORT, multiproc_dir=mp_dir)
