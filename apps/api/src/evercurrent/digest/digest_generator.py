"""Generates a member's personalized daily digest: gathers their top-scored
messages, open signals, and prior digests, then prompts Sonnet for the markdown."""

from __future__ import annotations

import json
import uuid
from importlib import resources
from typing import Any

import structlog
from jinja2 import Environment, StrictUndefined
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.digest import repository as digest_repo
from evercurrent.digest.schemas import (
    DigestContext,
    DigestDraft,
    DigestRecord,
)
from evercurrent.llm.client import LLMProvider
from evercurrent.llm.tiering import ModelTier

log = structlog.get_logger(__name__)

_PROMPT_PKG = "evercurrent.digest.prompts"
_TOP_N_SCORED = 20
_OPEN_SIGNALS_LIMIT = 20
_MAX_TOKENS = 2048
_PREVIEW_MAX_CHARS = 220

_jinja_env = Environment(
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,  # noqa: S701  prompt text, not HTML
)


def _load_system_prompt() -> str:
    return resources.files(_PROMPT_PKG).joinpath("system.txt").read_text(encoding="utf-8")


def _load_user_template() -> str:
    return resources.files(_PROMPT_PKG).joinpath("user.txt.j2").read_text(encoding="utf-8")


def _render_user_prompt(ctx: DigestContext) -> str:
    template = _jinja_env.from_string(_load_user_template())
    return template.render(
        member=ctx.member,
        project=ctx.project,
        day_index=ctx.day_index,
        top_scored_items=ctx.top_scored_items,
        open_signals=ctx.open_signals,
    )


def _filter_cited_ids(
    draft: DigestDraft,
    *,
    valid_signal_ids: set[uuid.UUID],
    valid_message_ids: set[uuid.UUID],
) -> DigestDraft:
    dropped_signals = [c for c in draft.signal_ids if c not in valid_signal_ids]
    dropped_msgs = [m for m in draft.message_ids if m not in valid_message_ids]
    if dropped_signals or dropped_msgs:
        log.warning(
            "digest.hallucinated_citations_dropped",
            dropped_signals=len(dropped_signals),
            dropped_messages=len(dropped_msgs),
        )

    filtered_signal_ids = [c for c in draft.signal_ids if c in valid_signal_ids]
    filtered_message_ids = [m for m in draft.message_ids if m in valid_message_ids]
    filtered_buckets: dict[str, list[uuid.UUID]] = {}
    for bucket, ids in draft.section_buckets.items():
        keep = [i for i in ids if i in valid_signal_ids or i in valid_message_ids]
        filtered_buckets[bucket] = keep

    return DigestDraft(
        content_md=draft.content_md,
        signal_ids=filtered_signal_ids,
        message_ids=filtered_message_ids,
        section_buckets=filtered_buckets,
    )


def _parse_draft(payload: Any) -> DigestDraft:
    if isinstance(payload, list):
        msg = "expected JSON object, got list"
        raise TypeError(msg)
    return DigestDraft.model_validate(payload)


def _stub_draft_from_scored(scored: list) -> DigestDraft:
    top = scored[:8]
    watch = scored[8:16]
    fyi = scored[16:24]

    def _bullets(items: list) -> str:
        if not items:
            return "_None._"
        lines = []
        for it in items:
            author = getattr(it, "author", "team")
            channel = getattr(it, "channel", "")
            urgency = getattr(it, "urgency", None) or "normal"
            preview = (getattr(it, "text", "") or "").replace("\n", " ").strip()
            if len(preview) > _PREVIEW_MAX_CHARS:
                preview = preview[: _PREVIEW_MAX_CHARS - 3] + "…"
            channel_tag = f"#{channel}" if channel else ""
            lines.append(
                f"- **{author}** {channel_tag} [{urgency}] — {preview}",
            )
        return "\n".join(lines)

    content_md = (
        "## Top priority\n"
        f"{_bullets(top)}\n\n"
        "## Watch-outs\n"
        f"{_bullets(watch)}\n\n"
        "## FYI\n"
        f"{_bullets(fyi)}\n"
    )
    message_ids = [s.message_id for s in (top + watch + fyi)]
    return DigestDraft(
        content_md=content_md,
        signal_ids=[],
        message_ids=message_ids,
    )


async def generate_digest(
    session: AsyncSession,
    llm: LLMProvider,
    *,
    project_member_id: uuid.UUID,
    day_index: int,
    phase: str,
    force: bool = False,
) -> DigestRecord | None:
    if not force:
        existing = await digest_repo.get_for_member_day(
            session,
            project_member_id=project_member_id,
            day_index=day_index,
        )
        if existing is not None:
            log.info(
                "digest.idempotent_hit",
                project_member_id=str(project_member_id),
                day_index=day_index,
            )
            return existing

    loaded = await digest_repo.load_member_profile(session, project_member_id)
    if loaded is None:
        msg = f"membership {project_member_id} not found"
        raise RuntimeError(msg)
    member, org_id = loaded

    project_id = await digest_repo.latest_project_id_for_org(session, org_id=org_id)
    project = await digest_repo.load_project_snapshot(
        session,
        phase=phase,
        project_id=project_id,
    )

    scored = await digest_repo.top_scored_items_for_member(
        session,
        project_member_id=project_member_id,
        limit=_TOP_N_SCORED,
    )
    signals = await digest_repo.open_signals_for_member_subsystems(
        session,
        project_id=project_id,
        owned_subsystems=member.owned_subsystems,
        eng_role=member.role,
        limit=_OPEN_SIGNALS_LIMIT,
    )

    if not scored and not signals:
        # Nothing synced for this member — don't fabricate a briefing. No digest
        # row, so the UI shows a clean "no digest yet" empty state.
        log.info(
            "digest.skip_empty",
            project_member_id=str(project_member_id),
            day_index=day_index,
        )
        return None

    ctx = DigestContext(
        member=member,
        project=project,
        day_index=day_index,
        top_scored_items=scored,
        open_signals=signals,
    )

    system_prompt = _load_system_prompt()
    user_prompt = _render_user_prompt(ctx)

    try:
        payload = await llm.complete_json(
            tier=ModelTier.DIGEST,
            system=system_prompt,
            prompt=user_prompt,
            max_tokens=_MAX_TOKENS,
            temperature=0.3,
        )
        draft = _parse_draft(payload)
    except (ValidationError, json.JSONDecodeError, ValueError, TypeError) as exc:
        # Malformed Sonnet JSON shouldn't lose the member their digest — fall
        # back to the deterministic stub built from their scored messages.
        log.warning(
            "digest.draft_failed_fallback",
            project_member_id=str(project_member_id),
            day_index=day_index,
            error=str(exc),
        )
        draft = _stub_draft_from_scored(scored)
    except Exception as exc:  # noqa: BLE001  fall back when LLM provider is down
        log.warning(
            "digest.llm_unavailable_fallback",
            project_member_id=str(project_member_id),
            day_index=day_index,
            error=str(exc),
        )
        draft = _stub_draft_from_scored(scored)

    valid_signal_ids = {c.signal_id for c in signals}
    valid_message_ids = {s.message_id for s in scored}
    draft = _filter_cited_ids(
        draft,
        valid_signal_ids=valid_signal_ids,
        valid_message_ids=valid_message_ids,
    )

    persisted = await digest_repo.upsert_digest(
        session,
        org_id=org_id,
        project_member_id=project_member_id,
        day_index=day_index,
        phase=phase,
        content_md=draft.content_md,
        signal_ids=draft.signal_ids,
        message_ids=draft.message_ids,
    )
    log.info(
        "digest.generated",
        digest_id=str(persisted.id),
        project_member_id=str(project_member_id),
        day_index=day_index,
        phase=phase,
        signal_count=len(draft.signal_ids),
        message_count=len(draft.message_ids),
    )
    return persisted
