"""Arq background jobs.

Task modules will be added under `tasks/` as later phases implement them
(enrich_messages, generate_digests, extract_decisions, advance_day,
ingest_doc). The Arq worker entrypoint is `worker.WorkerSettings`.
"""
