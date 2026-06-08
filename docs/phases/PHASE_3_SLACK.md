# Phase 3 — Slack ingest

## Goal

A user clicks "Connect Slack" → walks through Slack OAuth →
returns to our app with the bot installed in their workspace.
Their workspace's channels appear in `connector_channels`.
Messages in those channels stream in via the Slack Events API
webhook, land in `raw_events` first (untouched audit trail),
then normalised into `messages` with thread context preserved.
A one-shot backfill pulls the last 30 days of history for
selected channels.

By the end of this phase, the demo workspace's `#mech-design`,
`#qa-testing`, `#supply-chain`, and `#general` channels are
pumping real messages into the DB and you can see them in a
`SELECT * FROM messages` console.

## Why this phase, this order

Auth (phase 2) gave us tenant-scoped storage. Now we need
something to put in it. Slack is the first connector because
it's the highest-bandwidth source — the messages drive the
router agent (phase 5), which drives the cards (phase 6),
which drive the digest (phase 8). No Slack data, no demo.

Order inside the phase: OAuth install first (you can't list
channels without a token), channel discovery second (you can't
ingest events from channels you don't know about), Events
webhook third (now there's somewhere for messages to go), thread
hydration fourth (handles the "parent missing" edge case),
backfill last (a batch version of the same code path).

## Pre-requisites

- Phase 2 done (auth, RLS, `connectors` + `connector_channels`
  tables exist via earlier migrations or land in this phase)
- Slack app created at api.slack.com/apps
- Bot scopes: `channels:history`, `groups:history`, `chat:write`,
  `users:read`, `team:read`
- Event subscriptions: `message.channels`, `message.groups`
- Slack app's "Event Subscription Request URL" pointed at
  `<ngrok>/api/v1/webhooks/slack`
- `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`,
  `SLACK_REDIRECT_URI` populated in `.env`
- Fernet key in `.env` as `CONNECTOR_ENCRYPTION_KEY` for token storage

## Files touched

### New
- `apps/api/src/evercurrent/connectors/__init__.py`
- `apps/api/src/evercurrent/connectors/base.py` — `Connector` Protocol
- `apps/api/src/evercurrent/connectors/encryption.py` — Fernet wrapper
- `apps/api/src/evercurrent/connectors/slack/__init__.py`
- `apps/api/src/evercurrent/connectors/slack/types.py` — Pydantic event models
- `apps/api/src/evercurrent/connectors/slack/install.py` — OAuth flow
- `apps/api/src/evercurrent/connectors/slack/client.py` — `SlackClient` httpx wrapper
- `apps/api/src/evercurrent/connectors/slack/events.py` — webhook handler
- `apps/api/src/evercurrent/connectors/slack/signature.py` — HMAC verify
- `apps/api/src/evercurrent/connectors/slack/backfill.py` — 30-day pull
- `apps/api/src/evercurrent/api/routers/connectors.py`
- `apps/api/src/evercurrent/jobs/tasks/route_message.py` — stub for phase 5
- `apps/api/src/evercurrent/jobs/tasks/backfill_slack.py`
- `apps/api/alembic/versions/<rev>_connectors_messages_raw_events.py`
- `apps/api/seed_data/slack_seed.py` — populate demo workspace
- `apps/api/tests/integration/test_slack_signature.py`
- `apps/api/tests/integration/test_slack_events.py`
- `apps/api/tests/integration/test_slack_install.py`
- `apps/api/tests/integration/test_slack_threads.py`
- `apps/api/tests/integration/test_connector_encryption.py`

### Modified
- `apps/api/src/evercurrent/api/routers/webhooks.py` — add Slack handler
- `apps/api/src/evercurrent/main.py` — register connectors router
- `apps/api/pyproject.toml` — add `cryptography` (Fernet) if not present
- `.env.example` — add Slack + Fernet keys

### Deleted
- nothing

## Tasks

1. **Migration.** Create `connectors`, `connector_channels`,
   `raw_events`, `messages` per SYSTEM_DESIGN.md §2.3. Apply RLS
   policies to each. The `raw_events.UNIQUE (source, external_id)`
   and `messages.UNIQUE (source, external_id)` constraints are
   load-bearing for dedupe — make them explicit in the migration
   comment.
2. **Encryption helper.** `connectors/encryption.py`:
   ```python
   class TokenVault:
       def __init__(self, key: bytes) -> None:
           self._fernet = Fernet(key)
       def encrypt(self, plaintext: str) -> str: ...
       def decrypt(self, ciphertext: str) -> str: ...
   ```
   Wired into the DI container; reads `CONNECTOR_ENCRYPTION_KEY`.
3. **OAuth install kickoff.** `connectors/slack/install.py` +
   `POST /api/v1/connectors/slack/install`. Build the Slack OAuth
   URL with `client_id`, `scope=channels:history,groups:history,chat:write,users:read,team:read`,
   `redirect_uri`, and a CSRF `state` token (signed with our own
   secret, contains `org_id` + timestamp). Return `{ redirect_url }`.
4. **OAuth callback.** `GET /api/v1/connectors/slack/oauth/callback`.
   Verify `state`, exchange `code` for tokens via
   `https://slack.com/api/oauth.v2.access`, persist:
   ```python
   connector = Connector(
       org_id=...,
       kind="slack",
       external_team_id=resp["team"]["id"],
       credentials_secret=vault.encrypt(resp["access_token"]),
       installed_by=membership_id,
   )
   ```
   On unique constraint conflict (`(org_id, kind)`), update tokens
   in place — reinstall is allowed.
5. **Channel discovery.** Right after callback, enqueue
   `discover_slack_channels(connector_id)`. Worker calls
   `conversations.list` paginated, inserts into
   `connector_channels`, defaults `ingest = TRUE` for the first
   20 channels (the rest land disabled — user toggles in UI).
6. **Signature verification.** `connectors/slack/signature.py`:
   ```python
   def verify(body: bytes, timestamp: str, signature: str,
              signing_secret: str, *, now: float) -> bool:
       if abs(now - float(timestamp)) > 60 * 5:
           return False
       basestring = f"v0:{timestamp}:".encode() + body
       expected = "v0=" + hmac.new(
           signing_secret.encode(), basestring, hashlib.sha256
       ).hexdigest()
       return hmac.compare_digest(expected, signature)
   ```
   Constant-time compare, 5-minute skew window, raw body bytes.
7. **Events webhook.** `POST /api/v1/webhooks/slack`:
   - Read raw body bytes once: `body = await request.body()`.
   - URL verification challenge: if `payload["type"] ==
     "url_verification"`, return `{"challenge": payload["challenge"]}`
     immediately (no signature check needed — Slack accepts the
     challenge as proof of ownership).
   - Verify signature against `X-Slack-Signature` +
     `X-Slack-Request-Timestamp`. Reject 401 on failure.
   - Look up `connector` by `external_team_id = payload["team_id"]`.
     If missing or `status != 'active'`, return 200 (don't 404 —
     Slack will retry forever).
   - Set `app.current_org_id` from the connector's org.
   - Insert into `raw_events` with
     `(source='slack', external_id=event["event_ts"], payload=body_json)`.
     On unique constraint hit, swallow and return 200 (dedupe).
   - Enqueue `route_message(raw_event_id)` to Celery.
   - Return 200 in under 3 seconds (Slack retries past that).
8. **Message normalisation.** `route_message` task (stub for phase 5):
   - Read raw event.
   - If `event.subtype` is `message_changed` or `message_deleted`,
     skip for take-home scope.
   - Insert into `messages` with
     `external_id = event.ts`, `channel = event.channel`,
     `text = event.text`, `posted_at = datetime.fromtimestamp(float(event.ts))`,
     `author_display_name` resolved via cached `users.info`.
   - Thread linking: if `event.thread_ts` is present and
     `thread_ts != ts`, this is a reply. Look up parent message
     by `external_id = thread_ts`. If found, set
     `thread_root_id = parent.id`. If not found, fetch the
     parent via `conversations.replies`, insert it first, then
     link. The unique constraint on `(source, external_id)`
     prevents double-inserts if the parent arrives later via
     the normal webhook.
9. **Backfill task.** `backfill_slack_channel(connector_channel_id, days=30)`:
   - Paginate `conversations.history` with
     `oldest = now - days*86400`.
   - For each message, simulate the same code path the webhook
     uses: write `raw_events` row, write `messages` row. Dedupe
     by the unique constraint.
   - Fetch threads via `conversations.replies` for each parent
     that has `reply_count > 0`.
   - Triggered on demand via
     `POST /api/v1/connectors/{id}/channels/{channel_id}/backfill`.
10. **Demo seed script.** `apps/api/seed_data/slack_seed.py`:
    - Reads `SLACK_DEMO_BOT_TOKEN` from env (a token for a
      throwaway bot in the demo workspace, scopes: `chat:write`,
      `chat:write.customize` for username override).
    - Reads `seed_data/slack_messages.yaml` — N hand-written
      hardware-team messages per channel, ordered by day, with
      `author`, `channel`, `thread_index` fields.
    - Posts each message with `chat.postMessage`, overriding
      `username` and `icon_emoji` per author to simulate
      different team members.
    - Sleeps 250ms between posts to avoid Slack rate limits.
    - README in `seed_data/` documents how to create the
      `#mech-design`, `#qa-testing`, `#supply-chain`, and
      `#general` channels in the demo workspace and invite the
      bot.
11. **Connectors router.** Register
    `POST /api/v1/connectors/slack/install`,
    `GET /api/v1/connectors/slack/oauth/callback`,
    `GET /api/v1/connectors`,
    `POST /api/v1/connectors/{id}/channels/{external_id}` (toggle ingest),
    `POST /api/v1/connectors/{id}/channels/{external_id}/backfill`.
12. **ngrok handoff.** Document in `DEV_SETUP.md`: run
    `make ngrok`, copy URL, paste into Slack app's
    "Event Subscriptions → Request URL" and
    "OAuth & Permissions → Redirect URLs". URL changes on every
    `make ngrok` restart — that's a dev cost we accept.
13. **Commit.** `feat(phase-3): slack oauth install + events webhook + backfill`.

## Test plan

TDD-first.

1. **`test_slack_signature.py::test_valid_signature_accepted`** —
   Build the basestring, compute the right HMAC, call `verify`,
   assert True.
2. **`test_slack_signature.py::test_tampered_body_rejected`** —
   Same setup but mutate body by one byte. Assert False.
3. **`test_slack_signature.py::test_old_timestamp_rejected`** —
   Timestamp 6 minutes in the past, valid HMAC. Assert False
   (replay protection).
4. **`test_slack_signature.py::test_wrong_secret_rejected`** —
   HMAC computed with a different secret. Assert False.
5. **`test_slack_events.py::test_url_verification_challenge`** —
   POST `{"type":"url_verification","challenge":"abc"}`. Assert
   response is `{"challenge":"abc"}` and 200, even with no
   signature header.
6. **`test_slack_events.py::test_event_persisted_to_raw_events`** —
   POST a real-looking `message` event with valid signature.
   Assert one `raw_events` row exists with the right payload.
7. **`test_slack_events.py::test_duplicate_event_swallowed`** —
   POST the same event twice. Assert one `raw_events` row, both
   responses 200. Dedupe happens at the unique constraint, not
   in app code.
8. **`test_slack_events.py::test_event_for_unknown_team_returns_200`** —
   POST with `team_id` we've never seen. Assert 200 and no row
   inserted. We don't want Slack retrying.
9. **`test_slack_events.py::test_message_with_thread_ts_links_parent`** —
   Insert a parent message. POST a reply event whose `thread_ts`
   matches the parent's `ts`. After the route_message task
   runs, assert the reply's `thread_root_id` equals the parent's
   `id`.
10. **`test_slack_threads.py::test_orphan_reply_fetches_parent`** —
    POST a reply event whose parent we don't have yet. Mock the
    `conversations.replies` API to return the parent. Assert
    both rows exist after task completes, both with the right
    `thread_root_id`.
11. **`test_slack_install.py::test_oauth_state_csrf`** — Callback
    with mismatched `state` token returns 400.
12. **`test_slack_install.py::test_reinstall_updates_token`** —
    Run callback twice for the same org. Assert one
    `connectors` row, with the latest encrypted token.
13. **`test_connector_encryption.py::test_round_trip`** — Encrypt
    a token, persist to DB, read back, decrypt, assert equality.

## Definition of done

- [ ] `POST /api/v1/connectors/slack/install` returns a valid
      Slack OAuth URL
- [ ] OAuth callback persists encrypted token, kicks off channel
      discovery
- [ ] `connector_channels` populated after install, default 20
      channels with `ingest=true`
- [ ] `POST /api/v1/webhooks/slack` verifies HMAC signature,
      rejects bad signatures with 401
- [ ] URL verification challenge returns the right body
- [ ] Real Slack messages flow into `raw_events` then `messages`
- [ ] Thread replies correctly link to `thread_root_id`
- [ ] Orphan replies trigger parent fetch
- [ ] Dedupe verified by sending the same event twice
- [ ] Backfill task pulls 30 days into `messages`
- [ ] Seed script posts demo messages to the demo workspace
- [ ] `make lint` clean
- [ ] One commit on `feat/phase-3-slack` branch, merged to `main`

## Common pitfalls

- **Reading `request.body()` after `request.json()`.** FastAPI's
  body stream is one-shot. If a Pydantic body parameter consumes
  it first, HMAC verification fails. Read raw bytes, verify, then
  `json.loads` yourself.
- **Slack basestring includes the `v0:` prefix.** Format is
  `v0:{timestamp}:{body}`.
- **3-second timeout.** Slack retries any webhook >3s. Always:
  write raw event → enqueue → return. No LLM in the handler.
- **`hmac.compare_digest`, not `==`.** Constant-time compare.
- **Bot can't read history of channels it isn't in.** After
  install, invite the bot (`/invite @evercurrent`) before
  backfill. Document in the seed script.
- **`message.channels` vs `message.groups`.** Public channels
  emit the first, private channels the second. Subscribe to
  both, dispatch the same handler.
- **Subtype events.** `message_changed`, `channel_join`,
  `file_share` arrive as `message` events with a `subtype`.
  Filter at ingest: only persist when `subtype` is unset.
- **OAuth `state` token leak via referer.** HTTPS + short-lived
  signed state is sufficient for take-home.
- **Backfill rate limits.** `conversations.history` allows ~50
  req/min per workspace. Honour `Retry-After` from 429s.
- **ngrok URL changes on every restart.** Free tier URLs are
  ephemeral. Keep the ngrok process running for the demo window.

## Recap — what you'll be able to explain after this phase

- "How does data flow in from Slack?" → User OAuth-installs our
  app; bot token stored encrypted. Slack pushes every message
  event to `POST /api/v1/webhooks/slack`. We verify HMAC, write
  the raw payload to `raw_events`, enqueue a Celery task, return
  200 — all under 100ms. The task normalises into a `messages`
  row with thread context resolved.
- "Why write `raw_events` first?" → Audit trail and replay
  safety. We have the exact payload Slack sent, forever. If the
  normalisation logic changes (router agent v2 wants a field we
  didn't extract before), we replay over `raw_events`
  deterministically. Without it we'd re-fetch from Slack — rate
  limited, and deleted messages are gone.
- "How is signature verification done?" → HMAC-SHA256 over
  `v0:{timestamp}:{raw_body}` using the signing secret.
  `hmac.compare_digest` for constant-time compare; reject if
  timestamp is more than 5 minutes off (replay protection).
- "How are duplicates handled?" → Slack retries up to three
  times. We don't dedupe in app code — the unique constraint on
  `raw_events(source, external_id)` does it. Conflict → swallow
  → 200. Idempotent without any branching.
- "How are threads handled?" → Each event has a `ts` and an
  optional `thread_ts`. If `thread_ts` differs from `ts`, it's a
  reply. We look up parent by `external_id = thread_ts`; if
  missing, fetch via `conversations.replies` and insert first.
  The unique constraint handles races where the parent arrives
  through the normal webhook concurrently.
- "How are tokens stored?" → `connectors.credentials_secret` is
  a Fernet-encrypted blob keyed by `CONNECTOR_ENCRYPTION_KEY`.
  Production moves the key to AWS KMS; vault interface unchanged.

## Talking points (for the grill)

1. **"Raw first, parse second."** Every webhook payload lands
   verbatim in `raw_events` before any business logic touches
   it. Audit trail, replay safety, debugging gold.
2. **"Dedupe at the schema, not the app."** Unique constraint on
   `(source, external_id)` makes the handler idempotent for
   free. No `IF EXISTS` checks, no race windows.
3. **"Sub-3-second webhook handler."** Verify signature, write
   raw event, enqueue, return. The expensive work
   (router agent, embeddings, scoring) is async. Slack's
   retry budget is never burned.
4. **"Signature verification is non-negotiable."** Without it,
   anyone with our webhook URL can post fake messages into the
   DB. With it, signature failure → 401 → reject. HMAC over the
   raw bytes with a 5-minute window — both checks matter.
5. **"Thread context is preserved by FK + on-demand fetch."**
   `thread_root_id` is a self-referential FK. Orphan replies
   trigger a `conversations.replies` fetch. We never store a
   thread reply without its parent.
6. **"Encryption at rest for connector tokens."** Fernet today,
   KMS in production. The vault interface doesn't change.
7. **"Demo data is real Slack data."** No mocks. The seed
   script posts hand-written hardware-team messages to a real
   workspace, which we then ingest through the real webhook.
   Reviewer can sign in, see real messages, follow the trail
   from Slack → `raw_events` → `messages` → router agent (next
   phase).
