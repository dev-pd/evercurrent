# Phase 10 — Drive + PDF ingest

## Goal

Stand up the Google Drive connector. An admin clicks "Connect Drive",
goes through Google OAuth, picks one or more folders, and from that
moment every new PDF or Google Doc that lands in those folders gets
ingested: text extracted, chunked, embedded via Voyage `voyage-3-lite`
(512 dims), stored in `documents` + `document_chunks` with an HNSW
index, and run through a Haiku classifier that decides "is this a
decision-bearing doc?" — if yes, a Card is created with `card_sources`
citing the top chunks.

For the demo we ship a mock-Drive path too: a script that reads PDFs
from disk and runs the same `ingest_document` task, so the reviewer
doesn't need a live Drive setup to see the flow.

## Why this phase, this order

Phases 5-9 proved we can turn one Slack message into a Card, score it
per user, render it on a dashboard. That's the "events streaming in"
half of the product. The other half is "static documents the team has
already written" — the PRD, the BOM, the ECO log, the test reports.
Those are where decisions actually live, and they're what the digest
agent needs to cite when it explains *why* something matters.

Drive comes after the dashboard for two reasons. First, the dashboard
gives us a place to see ingest happen — Cards appear in real time as
docs land. Second, the embedding + chunking infrastructure we lay here
is the same plumbing the future Chat agent will reuse; building it
under a real ingest path forces us to confront the boring questions
(chunk size, batch limits, idempotency) before any chat UI hides
them.

Order inside the phase: OAuth install first (proves we can store a
token), folder picker second (proves we can list Drive resources),
push notifications third (proves Drive can reach us), ingest task
last (where most of the code lives).

## Pre-requisites

- Phase 2 (auth + RLS + `connectors` table from Phase 3 reused)
- Phase 3 (Slack OAuth pattern — Drive mirrors it)
- Phase 4 (MCP tools — the Haiku classifier calls `search_documents`
  to find related prior docs before deciding)
- Phase 6 (Cards builder — we'll add a doc-classifier code path here)
- Phase 8 (digest + SSE plumbing — we publish `document_ingested`)

## Files touched

### New

- `apps/api/src/evercurrent/connectors/drive/__init__.py`
- `apps/api/src/evercurrent/connectors/drive/install.py` — OAuth flow
- `apps/api/src/evercurrent/connectors/drive/client.py` — Drive API wrapper (download, list, watch)
- `apps/api/src/evercurrent/connectors/drive/watch.py` — register + renew push channels
- `apps/api/src/evercurrent/connectors/drive/webhook.py` — handler for Drive push notifications
- `apps/api/src/evercurrent/ingestion/__init__.py`
- `apps/api/src/evercurrent/ingestion/pdf_extract.py` — PyMuPDF text + page + bbox
- `apps/api/src/evercurrent/ingestion/chunking.py` — paragraph-aware sliding window
- `apps/api/src/evercurrent/ingestion/tasks.py` — Celery `ingest_document`
- `apps/api/src/evercurrent/ingestion/classifier.py` — Haiku "is this decision-bearing?"
- `apps/api/src/evercurrent/ingestion/prompts/classify_doc.txt`
- `apps/api/src/evercurrent/ingestion/schemas.py` — Pydantic classifier output
- `apps/api/seed_data/sample_pdfs/PRD_v1.pdf`
- `apps/api/seed_data/sample_pdfs/BOM_revC.pdf`
- `apps/api/seed_data/sample_pdfs/ECO-178_log.pdf`
- `apps/api/seed_data/sample_pdfs/thermal_test_report.pdf`
- `apps/api/seed_data/sample_pdfs/AlumWest_FAI.pdf`
- `apps/api/scripts/seed_pdfs.py` — uploads sample PDFs to a real Drive folder for demo
- `apps/api/scripts/mock_drive_ingest.py` — reads sample PDFs from disk, runs `ingest_document` directly
- `apps/api/tests/unit/test_chunking.py`
- `apps/api/tests/unit/test_pdf_extract.py`
- `apps/api/tests/integration/test_ingest_document.py`
- `apps/api/tests/integration/test_drive_webhook.py`
- `apps/api/tests/integration/test_watch_renewal.py`

### Modified

- `apps/api/pyproject.toml` — add `pymupdf`, `google-auth`, `google-auth-oauthlib`, `google-api-python-client`, pin versions
- `apps/api/src/evercurrent/rag/embedder.py` — add batched `embed_documents(texts: list[str])` that splits at 128 per Voyage call
- `apps/api/src/evercurrent/cards/builder.py` — add `maybe_create_card_from_doc(document_id)` entry point
- `apps/api/src/evercurrent/api/routers/webhooks.py` — add `POST /api/v1/webhooks/drive`
- `apps/api/src/evercurrent/api/routers/connectors.py` — add Drive install + callback + folder picker routes
- `apps/api/src/evercurrent/jobs/celery_tasks.py` — register `ingest_document`, `renew_drive_watches`
- `apps/api/src/evercurrent/jobs/beat_schedule.py` — daily `renew_drive_watches` at 02:00 UTC
- `apps/web/app/connectors/page.tsx` — add Drive tile + folder picker modal

### Deleted

- nothing

## Tasks

1. **Pin deps.** Add `pymupdf` (1.24+), `google-auth`, `google-auth-oauthlib`,
   `google-api-python-client` to `pyproject.toml`. `uv lock && uv sync`.
   Note locked versions in `docs/DECISIONS.md`.
2. **Drive OAuth install.** `POST /api/v1/connectors/drive/install`
   returns a Google consent URL with scopes `drive.readonly` +
   `drive.metadata.readonly`. The callback `GET /api/v1/connectors/drive/oauth/callback`
   exchanges the auth code for an access + refresh token, encrypts via
   the same KMS-style helper as Slack, persists a row in `connectors`
   (`kind='drive'`).
3. **Folder picker.** `GET /api/v1/connectors/drive/folders` lists the
   user's Drive folders (paged). `POST /api/v1/connectors/drive/folders`
   accepts `{folder_id, ingest: true}` and writes a `connector_channels`
   row per selected folder. The schema is general enough that "channel"
   maps cleanly onto "folder" — no new table needed.
4. **PyMuPDF extractor (`ingestion/pdf_extract.py`).** `extract_blocks(pdf_bytes: bytes) -> list[Block]`
   where `Block` is `{page: int, bbox: tuple[float, float, float, float],
   text: str}`. Use PyMuPDF's `page.get_text("blocks")`. Returns blocks
   in reading order. Headings are detected by font size (>= 1.3× median).
5. **Chunker (`ingestion/chunking.py`).** `chunk_blocks(blocks: list[Block],
   target_chars: int = 800, overlap_chars: int = 100) -> list[Chunk]`.
   Paragraph-aware: prefer to split at paragraph boundaries. Carries the
   nearest preceding heading into the chunk's `section` field. Overlap
   is implemented as character suffix of the previous chunk prepended to
   the next.
6. **Voyage batch embedder.** Extend `rag/embedder.py` with
   `async embed_documents(texts: list[str]) -> list[list[float]]` that
   splits the list at 128 per API call (Voyage's batch limit),
   `model="voyage-3-lite"`, `input_type="document"`. Returns embeddings
   in original order. Retries via tenacity on 429.
7. **Doc classifier (`ingestion/classifier.py`).** Calls Haiku via
   `llm/client.py` with a prompt that takes the document title, first
   3 chunks, and detected keywords. Returns Pydantic
   `DocClassification {is_decision: bool, kind: Literal['eco','test_report','prd','bom','other'],
   confidence: float, rationale: str}`. The classifier also calls the
   MCP tool `search_documents` (Phase 4) to find any prior related doc
   — useful for ECO-style docs that reference earlier ones.
8. **Celery task `ingest_document(connector_id, drive_file_id)`** in
   `ingestion/tasks.py`:
   1. Download bytes via the Drive API client.
   2. Reject if size > 50 MB; log + return.
   3. If `mimeType` is PDF: PyMuPDF extract. If Google Doc: use Drive's
      `files.export(mimeType='text/plain')`.
   4. Chunk.
   5. Voyage embed (batched).
   6. Persist a `documents` row (UNIQUE on `(source, external_id)` makes
      this idempotent), plus N `document_chunks` rows with embeddings.
   7. Run classifier. If `is_decision and confidence >= 0.7`, call
      `cards.builder.maybe_create_card_from_doc(document_id)`. Builder
      picks the top 3 chunks by relevance to the classifier's rationale
      as `card_sources`.
   8. Publish to Redis `events:<org_id>`: `{type: "document_ingested",
      payload: {document_id, title, card_id_or_null}}`.
9. **Drive push notifications.** `connectors/drive/watch.py` exposes
   `register_watch(folder_id, connector_id)` which calls
   `files.watch` against the folder with our public webhook URL,
   a fresh channel token, and a 7-day expiry. Persists `channel_id`,
   `channel_token`, `resource_id`, `expires_at` on the
   `connector_channels` row.
10. **Webhook handler.** `POST /api/v1/webhooks/drive`:
    1. Verify `X-Goog-Channel-Id` matches a row we own.
    2. Verify `X-Goog-Channel-Token` matches the row's stored token.
    3. Inspect `X-Goog-Resource-State` (one of `sync`, `add`, `change`).
       Skip `sync`. For `add`/`change`, call `files.list` against the
       folder with `modifiedTime > last_seen_modified_time` to get the
       changed files (Drive's webhook tells us *something* changed, not
       *what* — we diff).
    4. For each new file, enqueue `ingest_document(connector_id, file_id)`.
    5. Return 200 fast (< 50ms target).
11. **Watch renewal cron.** `renew_drive_watches` runs daily at 02:00
    UTC via Celery Beat. Finds any channel where `expires_at < now() +
    36 hours`, calls `files.watch` again to register a new channel,
    updates the row. The 36-hour buffer means a missed run still
    leaves us a day to recover.
12. **Mock-drive script for demo.** `apps/api/scripts/mock_drive_ingest.py`
    reads the 5 sample PDFs from `seed_data/sample_pdfs/`, fabricates
    `connector_id` + `drive_file_id` per file, and calls
    `ingest_document` directly via Celery. This is the path the demo
    uses when there's no live Drive set up.
13. **Real-drive script for demo.** `apps/api/scripts/seed_pdfs.py`
    uses the installed Drive connector for the demo org to upload the
    same 5 sample PDFs to the chosen folder, triggering the real
    webhook path.
14. **Frontend Drive tile.** Update `apps/web/app/connectors/page.tsx`
    to add a Drive tile that mirrors the Slack one: "Connect" button →
    redirects through OAuth, post-install shows a folder picker modal.
15. **Lint + test.** `make lint && make test-integration` green.
16. **Commit.** `feat(phase-10): drive connector + pdf ingest + doc-classifier card path`.

## Test plan

TDD. Tests live under `tests/unit/` for pure functions and
`tests/integration/` for anything that touches Postgres, Celery, or a
mocked Drive client.

Order tests are written:

1. `test_pdf_extract.py::test_pdf_extract_returns_blocks_with_page_and_bbox`
   — feeds a fixture PDF, asserts blocks come back with `page` int
   and `bbox` 4-tuple.
2. `test_chunking.py::test_chunking_respects_overlap` — asserts the
   last N chars of chunk[i] appear as prefix of chunk[i+1] when
   overlap is set.
3. `test_chunking.py::test_chunking_carries_section_heading` —
   chunks under a heading inherit `section`; chunks before any
   heading get `section=None`.
4. `test_chunking.py::test_chunking_handles_paragraph_smaller_than_overlap`
   — tiny final paragraph doesn't crash, just becomes its own short
   chunk.
5. `test_chunking.py::test_voyage_batch_splits_at_128` — feed 300
   chunks to the embedder, assert the stubbed Voyage client was
   called 3 times (128, 128, 44).
6. `test_ingest_document.py::test_ingest_idempotent_by_external_id`
   — run `ingest_document` twice with the same `(source, external_id)`;
   second run does not create duplicate `documents` or `document_chunks`
   rows.
7. `test_ingest_document.py::test_classifier_creates_card_for_eco_doc`
   — feed the ECO-178 fixture PDF (synthetic, contains "ECO" + "decided
   to switch from"), assert one `cards` row + matching `card_sources`.
8. `test_ingest_document.py::test_classifier_skips_prd_doc` — feed
   the PRD fixture, assert no `cards` row is created (PRD is
   general-context, not decision-bearing).
9. `test_drive_webhook.py::test_webhook_rejects_bad_channel_token` —
   POST to `/webhooks/drive` with a wrong `X-Goog-Channel-Token`,
   assert 401, no task enqueued.
10. `test_drive_webhook.py::test_webhook_enqueues_ingest_on_add` —
    valid request with `X-Goog-Resource-State: add`, assert
    `ingest_document` was scheduled.
11. `test_watch_renewal.py::test_watch_renewal_runs_before_expiry` —
    seed two channels (one expiring in 24h, one in 6 days), run
    `renew_drive_watches`, assert only the soon-to-expire one was
    renewed.

External clients (Drive API, Voyage) are stubbed via fixtures. The
real network paths run from `scripts/` in dev only.

## Definition of done

- [ ] Drive OAuth install round-trips and stores an encrypted token
- [ ] Folder picker lists folders, persists selection to
      `connector_channels`
- [ ] `files.watch` registers a push channel; webhook handler verifies
      both `X-Goog-Channel-Id` and `X-Goog-Channel-Token`
- [ ] PyMuPDF extractor returns text + page + bbox per block
- [ ] Chunker respects target size, overlap, and carries section heading
- [ ] Voyage embedder batches at 128 per call, returns vectors in
      original order
- [ ] `documents` + `document_chunks` populated; HNSW index in use
- [ ] Classifier creates a Card for ECO-style docs, skips general PRDs
- [ ] `mock_drive_ingest.py` runs end-to-end against the 5 sample PDFs
- [ ] `seed_pdfs.py` uploads the 5 sample PDFs to a real Drive folder
      and the real webhook path picks them up
- [ ] `renew_drive_watches` cron renews channels before expiry
- [ ] 30-page PDF goes from "webhook fires" to "Card visible on
      dashboard" in < 5s end-to-end on a laptop
- [ ] All TDD tests green
- [ ] `make lint` and `make test-integration` green
- [ ] One commit on `feat/phase-10-drive` branch, merged to `main`

## Common pitfalls

- **PyMuPDF licensing.** PyMuPDF is AGPL. Fine for this take-home and
  for internal use; if EverCurrent ever ships as a sold product we'd
  need to swap to a commercial license or replace it. Note in
  `DECISIONS.md`. Don't sneak the import into a place we later regret.
- **Drive `files.watch` expects a verified domain in production.** For
  dev, the ngrok HTTPS URL is enough because we register it directly.
  Don't waste an hour trying to get Google to "verify" an ngrok URL —
  it's not required for the watch API itself, only for OAuth consent
  branding.
- **Webhook tells you *something* changed, not *what*.** Drive push
  is a kick, not a payload. The handler has to diff. Easy to forget
  and end up re-ingesting every file every time.
- **`X-Goog-Resource-State: sync` arrives once per channel.** That's
  the initial handshake. If you treat it as a change, you'll ingest
  every file in the folder at registration. Skip it.
- **Google Docs are not PDFs.** Use `files.export(mimeType='text/plain')`
  for Docs. PyMuPDF will choke on the Google Doc binary format.
- **Channel expiry is 7 days max, but Google may revoke earlier.**
  The renewal cron should handle "register failed because the channel
  is gone" by treating it as a fresh registration, not a retry.
- **Voyage 128 batch limit is silent.** Send 200 in one call and you
  get a confusing error. The batcher must split before sending.
- **HNSW index needs the column populated.** Trying to query a chunk
  whose `embedding` was never written returns nothing — easy to
  mistake for a retrieval bug.
- **Idempotency by `(source, external_id)` is the only safe key.**
  Drive file IDs are stable; modified times are not. Re-running the
  task on the same file must be a no-op.

## Recap — what you'll be able to explain after this phase

- "Why PyMuPDF over pdfplumber or Unstructured?"
  → Speed and structural data. PyMuPDF is 5-10× faster on a typical
    30-page engineering PDF and gives you position (page + bbox) in
    addition to text. We use bbox today only for chunk attribution;
    tomorrow it lets us draw a highlight on the embedded viewer
    when a Card cites a chunk. pdfplumber is layout-aware but
    slower; Unstructured is general-purpose but overkill for the
    "PDF + Google Doc only" surface we have.
- "Why ~800-char chunks with 100 overlap?"
  → It matches Voyage's retrieval sweet spot empirically (their docs
    suggest 400-1000 tokens; 800 chars is ~150 tokens, near the
    short end where recall and precision both stay high). 800 chars
    is also "about a paragraph" of engineering prose. Overlap of
    100 chars catches the case where a key sentence straddles a
    chunk boundary.
- "Why voyage-3-lite over OpenAI ada-002?"
  → Three reasons: cost (~5× cheaper per million tokens), dimension
    count (512 vs 1536 — smaller index, faster ANN, less storage),
    and retrieval quality on technical text is comparable in our
    spot-checks. We're not optimising for benchmark wins; we want
    decent retrieval at a price that lets us re-embed when the
    model improves.
- "Why push notifications instead of polling Drive?"
  → Latency and bandwidth. Polling at any reasonable interval (5
    minutes?) means a 5-minute lag between "engineer drops a PDF"
    and "Card on dashboard." Push gets it under 5 seconds. We also
    avoid the polling burst on a folder with hundreds of files.
- "Why a mock-drive path for the demo?"
  → Setting up a real Drive OAuth app, a folder, ngrok forwarding,
    and an actual file drop is 15 minutes of friction for the
    reviewer. The mock path takes the same `ingest_document` task
    and feeds it the 5 sample PDFs directly. The reviewer sees the
    exact same end state — Cards on the dashboard — without
    needing a Google account.
- "What does the classifier actually decide?"
  → It picks one of {eco, test_report, prd, bom, other} and a
    boolean `is_decision`. ECOs and test reports are decision-
    bearing (something changed, someone signed off). PRDs and BOMs
    are general context. The boolean is what gates Card creation.
    The kind is stored on the `documents` row for future filtering.

## Talking points (for the grill)

1. **"Drive connector mirrors Slack."** Same OAuth pattern, same
   `connectors` + `connector_channels` schema, same encrypted-token
   approach. No new tenancy machinery.
2. **"Idempotent ingest by `(source, external_id)`."** Re-running the
   task on the same file is a no-op. Important because Drive will
   ping us for `change` events that don't actually change content.
3. **"Voyage batch at 128."** The embedder owns the batching; tools
   above it just pass `list[str]`. The 128 cap is Voyage's, not ours.
4. **"Watch renewal cron with a 36-hour buffer."** Channels expire
   in 7 days; we renew at day 5.5. A missed run still leaves recovery
   room.
5. **"PyMuPDF for speed + position data."** Reading order, page,
   bbox in one pass. Sets us up for highlighted citations later.
6. **"Mock-drive path for the demo."** No reviewer setup. Same task,
   same end state.
7. **"Classifier is Haiku, not Sonnet."** It's a yes/no with a kind
   tag. Cheap, fast, good enough; we save Sonnet for the digest.
8. **"Card sources point to chunks, not files."** Citations resolve
   to the exact paragraph the LLM judged decision-bearing, not
   "somewhere in the 30-page PDF."
