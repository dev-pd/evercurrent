# Phase 11 — Notify (Slack DM)

## Goal

Close the loop. When the digest is ready, deliver it as a Slack DM to
the user. When an urgent Card is created and the user's score crosses
the threshold, send an immediate DM if their subscription is enabled
and we're not inside quiet hours. The user controls all of this from
a Settings page: which notification kinds they want, the local
timezone, and the quiet-hour window.

End state: a reviewer opens the dashboard at 08:00, sees the digest;
their Slack also pings with the same digest as a Block Kit DM. Drop a
critical Card; a second DM lands.

## Why this phase, this order

The dashboard (Phase 9) is where the user reads in pull mode. Slack
DM is where the platform reaches them in push mode. Without push,
EverCurrent is a website you have to remember to visit — that fails
the "Sarah opens it twice a day, gets the value, leaves" promise from
the PRD. Conversely, push without quiet hours and per-user
subscriptions is exactly the notification spam every engineer hates;
it has to ship with controls or it doesn't ship at all.

This is last before polish because everything it needs is already in
place: Slack OAuth tokens (Phase 3), digests (Phase 8), `urgency` on
Cards (Phase 6), score thresholds per member (Phase 7), and the
`subscriptions` + `notifications` tables (Phase 2's schema).

Order inside the phase: subscription model + API first (proves the
control surface), Block Kit renderer second (proves we can format),
delivery task third (the real work), quiet-hour logic and 429 retry
fourth (the production-ready details), FE Settings page last.

## Pre-requisites

- Phase 3 (Slack OAuth + bot token stored per org)
- Phase 6 (`cards.urgency` field)
- Phase 7 (per-member scores)
- Phase 8 (`digests` rows + `digest_ready` SSE event)
- Phase 9 (FE shell with Settings nav entry)

## Files touched

### New

- `apps/api/src/evercurrent/notify/__init__.py`
- `apps/api/src/evercurrent/notify/slack_deliver.py` — `chat.postMessage` calls
- `apps/api/src/evercurrent/notify/block_kit.py` — digest markdown → Block Kit blocks
- `apps/api/src/evercurrent/notify/quiet_hours.py` — timezone-aware quiet-window math
- `apps/api/src/evercurrent/notify/repository.py` — `notifications` + `subscriptions` reads/writes
- `apps/api/src/evercurrent/api/routers/subscriptions.py` — GET + PUT
- `apps/api/tests/unit/test_block_kit.py`
- `apps/api/tests/unit/test_quiet_hours.py`
- `apps/api/tests/integration/test_deliver_digest_dm.py`
- `apps/api/tests/integration/test_deliver_urgent_dm.py`
- `apps/api/tests/integration/test_subscriptions_router.py`
- `apps/web/app/subscriptions/page.tsx`
- `apps/web/components/subscriptions/subscription-toggle.tsx`
- `apps/web/components/subscriptions/quiet-hours-picker.tsx`
- `apps/web/hooks/use-subscriptions.ts`

### Modified

- `apps/api/src/evercurrent/jobs/celery_tasks.py` — add `deliver_digest_dm`, `deliver_urgent_dm`
- `apps/api/src/evercurrent/digest/agent.py` — on `digest_ready` SSE publish, also enqueue `deliver_digest_dm(digest_id)`
- `apps/api/src/evercurrent/cards/builder.py` — on `urgency='critical'` Card creation, enqueue `deliver_urgent_dm(card_id, membership_id)` per qualifying member
- `apps/api/src/evercurrent/db/models.py` — extend `org_memberships` with `quiet_start: TIME`, `quiet_end: TIME` (Alembic migration)
- `apps/api/alembic/versions/` — new migration for quiet-hour columns

### Deleted

- nothing

## Tasks

1. **Alembic migration.** Add `quiet_start TIME NOT NULL DEFAULT '22:00'`
   and `quiet_end TIME NOT NULL DEFAULT '07:00'` to `org_memberships`.
   The existing `timezone` column already lives there from Phase 2.
2. **Subscriptions API.**
   - `GET /api/v1/subscriptions` returns
     `{items: [{kind, value, enabled}], quiet_start, quiet_end, timezone}`.
     Lives in `api/routers/subscriptions.py`.
   - `PUT /api/v1/subscriptions` replaces the full subscription set
     for the caller plus updates quiet-hour fields. Uses a transaction
     so partial writes are impossible.
   - Pydantic schemas in `api/routers/subscriptions.py`:
     `SubscriptionItem {kind: Literal['morning_digest', 'urgent_immediate',
     'weekly_summary', 'mention', 'subsystem_decision'], value: str | None,
     enabled: bool}`.
3. **Block Kit renderer (`notify/block_kit.py`).** Pure function
   `digest_to_blocks(digest: Digest, member: Membership) -> list[dict]`:
   - Header block: `"Day {N} · {phase} · {date}"`.
   - Divider.
   - Section per priority bucket (Top priority, Watch-outs, FYI).
     Each item is a Slack section block with markdown text + a
     "View thread" or "Open card" button linking to the web app.
   - Footer with a single small-text line for "Reply with feedback or
     thumbs up to retrain."
   - Truncate any single section to 3000 chars (Slack's per-block
     limit). Long bodies link out to the web Card.
4. **Quiet-hour math (`notify/quiet_hours.py`).** Pure function
   `is_quiet(now_utc: datetime, member: Membership) -> bool`:
   - Convert `now_utc` to the member's local timezone via `zoneinfo`.
   - Compute whether the local time is within `[quiet_start, quiet_end)`.
   - Handle the wrap case (`22:00 → 07:00` spans midnight) by checking
     `now >= quiet_start or now < quiet_end`.
   - Function `next_active_time(now_utc, member) -> datetime` returns
     the next UTC moment the user is *not* in quiet hours.
5. **Delivery task `deliver_digest_dm(digest_id)`** in
   `jobs/celery_tasks.py`:
   1. Load digest + membership + subscriptions via the notify repo.
   2. If subscription `morning_digest` is disabled or missing →
      record a `notifications` row with `delivered_via='skipped'`,
      return.
   3. If `is_quiet()` is true → reschedule the task at
      `next_active_time()` via Celery `apply_async(eta=...)`. Increment
      a `defer_count` log field.
   4. Render Block Kit.
   5. Call Slack `chat.postMessage` with `channel=member.slack_user_id`
      (DMing a user uses their user_id directly; Slack opens or reuses
      the IM channel).
   6. Handle the response:
      - 200 → persist a `notifications` row with `kind='morning_digest',
        sent_at=now(), channel='slack_dm', payload={ts, channel}`.
      - 429 → read `Retry-After` header, raise `Retry(countdown=...)`
        so Celery handles backoff.
      - 4xx other → log + persist as `delivered_via='failed'`, do not
        retry.
6. **Delivery task `deliver_urgent_dm(card_id, membership_id)`:**
   1. Load card + member + subscriptions.
   2. If subscription `urgent_immediate` is disabled → skip + log.
   3. If `is_quiet()` and the subscription does *not* have the
      `override_quiet=true` value → defer.
   4. If `is_quiet()` and override is set → send anyway. (User opted
      in to the override for the alert use case.)
   5. Render a smaller Block Kit message: title, one-line summary,
      "Open card" button, "View thread" button.
   6. Send via `chat.postMessage`. Same retry rules as digest.
   7. Persist `notifications` row with `kind='urgent_immediate'`.
7. **Hook from digest.** In `digest/agent.py`, after the
   `digest_ready` SSE publish, enqueue `deliver_digest_dm(digest.id)`
   on the Celery queue.
8. **Hook from cards.** In `cards/builder.py`, when a Card is
   created with `urgency='critical'` (resolved by the Phase 5/6
   pipeline), look up all `project_members` whose `scores.score`
   for the underlying message exceeds the per-org threshold, and
   enqueue `deliver_urgent_dm` per qualifying member.
9. **Frontend subscriptions page.**
   - `apps/web/app/subscriptions/page.tsx` server component fetches
     current subscriptions + quiet-hour settings.
   - `SubscriptionToggle` (client component): one labeled switch per
     kind. Optimistic update via TanStack Query mutation; rolls back
     on error.
   - `QuietHoursPicker` (client component): two time pickers (start +
     end) plus a timezone select prefilled from the member row.
   - The page batches all changes into a single `PUT` on save.
10. **Lint + test.** `make lint && make test` green.
11. **Commit.** `feat(phase-11): slack DM delivery + subscriptions + quiet hours`.

## Test plan

TDD. Pure functions get unit tests; anything that touches the
Slack SDK gets an integration test with the SDK stubbed.

Order tests are written:

1. `test_block_kit.py::test_digest_dm_renders_block_kit_correctly`
   — feed a fixture digest with 3 priority buckets, assert the
   resulting block list has the expected shape (header, divider, 3
   section groups, footer), and each section block's text is under
   3000 chars.
2. `test_quiet_hours.py::test_quiet_hours_defers_delivery` — call
   `is_quiet()` with `now = 2026-06-07 04:00 UTC` and a US/Pacific
   member (local = 21:00 prior day) whose quiet window is
   `22:00 → 07:00`. Assert false (still 21:00). Then `now = 06:00 UTC`
   (local = 23:00). Assert true.
3. `test_quiet_hours.py::test_quiet_hours_respects_user_timezone` —
   same physical time, two members in different timezones; one is in
   quiet hours, the other is not. Assert the function returns
   different results.
4. `test_quiet_hours.py::test_quiet_hours_wrap_across_midnight` —
   quiet window `22:00 → 07:00` correctly identifies `01:00 local` as
   quiet and `08:00 local` as active.
5. `test_deliver_urgent_dm.py::test_urgent_overrides_quiet_when_enabled`
   — subscription has `value='override_quiet'`. `is_quiet()` returns
   true. Assert the DM was sent anyway and the `notifications` row
   is persisted.
6. `test_deliver_digest_dm.py::test_429_retry_with_backoff` — stub
   Slack to return 429 with `Retry-After: 30` once then 200. Assert
   the task retried after ~30s (mocked clock) and the second send
   succeeded.
7. `test_deliver_digest_dm.py::test_subscription_disabled_skips_send`
   — member has `morning_digest` disabled. Run task. Assert no
   `chat.postMessage` call and a `notifications` row with
   `delivered_via='skipped'`.
8. `test_deliver_digest_dm.py::test_notifications_row_persisted_with_sent_at`
   — happy path: assert the row has `sent_at`, `channel='slack_dm'`,
   `payload` includes Slack's returned `ts`.
9. `test_subscriptions_router.py::test_subscription_put_replaces_full_set`
   — seed a member with 3 subscriptions; PUT 2 different ones; assert
   the old 3 are gone and the 2 new ones are present. Single
   transaction, no partial state on midway failure.

Slack SDK is stubbed by injecting a fake `WebClient` via the DI
container, the same pattern Phase 3 used for the Events API.

## Definition of done

- [ ] Alembic migration adds `quiet_start` + `quiet_end` to
      `org_memberships` with sensible defaults
- [ ] `GET /api/v1/subscriptions` returns the user's current set +
      quiet config
- [ ] `PUT /api/v1/subscriptions` replaces the set atomically
- [ ] `deliver_digest_dm` task fires after digest is ready, respects
      subscription + quiet hours
- [ ] `deliver_urgent_dm` task fires on critical Card creation for
      qualifying members
- [ ] Block Kit renderer produces a digest that looks correct in a
      real Slack workspace
- [ ] Quiet-hour logic handles timezones and the midnight wrap case
- [ ] Critical subscriptions can override quiet hours when the user
      opts in
- [ ] 429 from Slack triggers exponential backoff via Celery retry
- [ ] Every send (success, skip, fail) writes a `notifications` row
- [ ] Settings page lets the user toggle subscriptions + pick quiet
      hours
- [ ] All TDD tests green
- [ ] `make lint` and `make test` green
- [ ] One commit on `feat/phase-11-notify` branch, merged to `main`

## Common pitfalls

- **DMing a user by `slack_user_id` works only if our app is in their
  workspace.** That's guaranteed because we installed via OAuth, but
  if `slack_user_id` is null on `org_memberships` (user joined via
  Clerk but never linked their Slack), the task should skip
  gracefully, not crash.
- **Slack timezones vs Python timezones.** Slack's user profile has
  a `tz` string like `"America/Los_Angeles"` — that's what `zoneinfo`
  expects. Don't try to compute UTC offsets manually; daylight
  savings will bite.
- **Block Kit 3000-char limit per section.** A long digest item will
  silently truncate or be rejected. The renderer must enforce the
  limit before sending; over-long items become "see the full Card →"
  link-outs.
- **Quiet-hour deferral creates a tail.** If 200 users all have quiet
  hours `22:00 → 07:00` US/Pacific, 200 tasks all wake up at
  `07:00 PT` and hammer Slack. Add a small jitter (`random.uniform(0,
  300)` seconds) to `next_active_time` to spread the load.
- **Retry-After interpretation.** Slack sends it in seconds. Celery's
  `countdown=` is also seconds. Don't multiply by 1000 (it's not ms).
- **Block Kit buttons need stable URLs.** `Open card` button URL
  must point at the web app's `/decisions/[id]` route, not the API.
  Read `WEB_PUBLIC_URL` from env, not hardcoded.
- **PUT replace semantics need a single transaction.** A naive
  "delete all rows, insert new rows" without a transaction loses the
  user's settings on a midway crash.
- **Marking subscriptions disabled vs deleting.** Keep the row,
  toggle `enabled`. Auditability + future analytics. Don't lose the
  fact that the user once subscribed.

## Recap — what you'll be able to explain after this phase

- "Why Slack Block Kit instead of plain text?"
  → Three reasons. First, Block Kit lets us put real buttons in the
    message — "Open card" jumps to the dashboard in one tap; "View
    thread" jumps to the Slack thread. With plain text we'd just
    paste URLs and the user copy-pastes. Second, scanability: header
    + dividers + section blocks make the priority buckets visually
    distinct. A wall of text doesn't get read. Third, it sets up the
    interactive future — Block Kit messages can host buttons that
    POST back to our API, so "Mark resolved" or "Snooze" become a
    one-click action later with the same surface.
- "Why persist a row in `notifications` for every send?"
  → Audit, retention, and analytics. Audit because SOC 2 / ITAR
    customers will ask "what did the system send to my user?".
    Retention because we offer "I never received the digest, resend
    it" — we look up the row, not the agent state. Analytics because
    the open + click columns let us compute retention metrics from
    the PRD's success table (open rate > 70%).
- "Why are quiet hours respected by default?"
  → Notification fatigue is the death-spiral for any push surface.
    The first time we wake an engineer at 02:00 with a "FYI" digest,
    they uninstall. Defaulting `22:00 → 07:00` in the user's local
    timezone is the safe baseline. The user can tighten or widen it
    in Settings. We log the deferred-then-sent count so we know how
    much delay we're injecting.
- "Why does 'critical' override quiet hours, but only if the user
  opts in?"
  → The whole point of an urgent path is that some events warrant an
    interruption — "ECO-178 blocks DVT exit and you authored it" is
    worth waking someone up *if* the user agreed it is. Opt-in keeps
    us honest: we don't sneakily bypass quiet hours; the user
    explicitly enabled `urgent_immediate.override_quiet=true` when
    they want that behaviour. Default off.
- "Why split into two delivery tasks instead of one?"
  → Different triggers, different payloads, different retry
    sensitivities. Digest is once-a-day per user, scheduled, content
    is markdown the agent already produced. Urgent is event-driven,
    immediate, content is a single Card. Sharing a task would mean
    branching the body all the way through and obscuring the
    intent. Two clean functions read better.
- "What stops us from spamming a user with 50 urgent DMs?"
  → Two limits in this phase, more on the roadmap. (1) The score
    threshold per member: only members whose relevance score
    crosses the org-wide critical threshold get a DM, which already
    filters most messages. (2) `notifications` table makes
    "max 1 critical per hour per user" a one-query SQL check that we
    will add when we see the first volume-spike incident.

## Talking points (for the grill)

1. **"Block Kit, not plain text."** Buttons, dividers, scanability.
   Sets up interactive notifications later for free.
2. **"Quiet hours are timezone-aware and wrap-aware."** zoneinfo, not
   manual offsets. `22:00 → 07:00` correctly identifies `01:00` as
   quiet.
3. **"Subscriptions PUT is transactional."** Whole set replaces in
   one query. No partial state on crash.
4. **"Every send writes a notification row."** Audit + retention +
   click analytics in one table.
5. **"Critical overrides quiet hours, but only on opt-in."** The
   user signs off on the interruption.
6. **"429 retry uses Celery's countdown."** Honour Slack's
   `Retry-After`; no custom backoff loop.
7. **"DMing by `slack_user_id` is one API call."** Slack opens or
   reuses the IM channel server-side. No "open conversation" step.
8. **"Jitter on quiet-hour deferral."** When 200 users wake at
   `07:00`, we don't fire 200 sends at the same millisecond.
