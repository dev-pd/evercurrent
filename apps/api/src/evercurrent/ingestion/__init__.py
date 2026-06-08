"""Document ingestion pipeline.

Phase 1 used this package for synthetic-data generation; the seed
helpers now live in `apps/api/seed_data/` directly. Phase 10 reclaims
the package for the real Drive + PDF ingest path:

- `pdf_extract` — PyMuPDF block extraction
- `chunking`    — paragraph-aware sliding-window chunker
- `classifier`  — Haiku call: decision-bearing vs general context
- `tasks`       — async `ingest_document(connector_id, drive_file_id)`
                  used by both Drive webhook and the mock-drive path
- `schemas`     — Pydantic strict result of the classifier
"""
