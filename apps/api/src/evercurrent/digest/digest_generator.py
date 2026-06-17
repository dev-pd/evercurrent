from __future__ import annotations

import json
import uuid
from importlib import resources
from typing import Any

import structlog
from jinja2 import Environment, StrictUndefined
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.digest import repository as digest_repo
from evercurrent.digest.schemas import (
    DigestContext,
    DigestDraft,
    DigestRecord,
    MemberProfile,
    ProjectSnapshot,
)
from evercurrent.llm.client import LLMProvider
from evercurrent.llm.tiering import ModelTier

log = structlog.get_logger(__name__)

_PROMPT_PKG = "evercurrent.digest.prompts"
_TOP_N_SCORED = 20
_PRIOR_DIGESTS_LIMIT = 3
_OPEN_CARDS_LIMIT = 20
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
        open_cards=ctx.open_cards,
        prior_digests=ctx.prior_digests,
    )


async def _load_member_profile(
    session: AsyncSession,
    project_member_id: uuid.UUID,
) -> tuple[MemberProfile, uuid.UUID] | None:
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, org_id, display_name, role, eng_role, "
                    "owned_subsystems, topic_weights, timezone "
                    "FROM org_memberships WHERE id = :id",
                ),
                {"id": str(project_member_id)},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    org_id = uuid.UUID(str(row["org_id"]))

    topic_weights: dict[str, float] = dict(row["topic_weights"] or {})
    subsystems: list[str] = list(row["owned_subsystems"] or [])
    eng_role = row["eng_role"] or row["role"]

    profile = MemberProfile(
        project_member_id=uuid.UUID(str(row["id"])),
        display_name=str(row["display_name"] or ""),
        role=str(eng_role or "member"),
        timezone=str(row["timezone"] or "UTC"),
        owned_subsystems=subsystems,
        topic_weights=topic_weights,
    )
    return profile, org_id


async def _load_project_snapshot(
    session: AsyncSession,
    *,
    phase: str,
    project_id: uuid.UUID | None,
) -> ProjectSnapshot:
    if project_id is None:
        return ProjectSnapshot(
            project_id=uuid.UUID(int=0),
            name="(unknown)",
            current_phase=phase,
            phase_concerns=[],
        )
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, name, current_phase, phase_concerns FROM projects WHERE id = :id",
                ),
                {"id": str(project_id)},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return ProjectSnapshot(
            project_id=project_id,
            name="(unknown)",
            current_phase=phase,
            phase_concerns=[],
        )
    concerns_raw = row["phase_concerns"] or {}
    concerns_list = list(concerns_raw.get(phase, [])) if isinstance(concerns_raw, dict) else []
    return ProjectSnapshot(
        project_id=uuid.UUID(str(row["id"])),
        name=str(row["name"] or "(unknown)"),
        current_phase=str(row["current_phase"] or phase),
        phase_concerns=[str(c) for c in concerns_list],
    )


async def _resolve_project_id_for_member(
    session: AsyncSession,
    *,
    project_member_id: uuid.UUID,
    org_id: uuid.UUID,
) -> uuid.UUID | None:
    _ = project_member_id
    row = (
        await session.execute(
            text(
                "SELECT id FROM projects WHERE org_id = :oid ORDER BY created_at DESC LIMIT 1",
            ),
            {"oid": str(org_id)},
        )
    ).first()
    if row is None:
        return None
    return uuid.UUID(str(row[0]))


def _filter_cited_ids(
    draft: DigestDraft,
    *,
    valid_card_ids: set[uuid.UUID],
    valid_message_ids: set[uuid.UUID],
) -> DigestDraft:
    dropped_cards = [c for c in draft.card_ids if c not in valid_card_ids]
    dropped_msgs = [m for m in draft.message_ids if m not in valid_message_ids]
    if dropped_cards or dropped_msgs:
        log.warning(
            "digest.hallucinated_citations_dropped",
            dropped_cards=len(dropped_cards),
            dropped_messages=len(dropped_msgs),
        )

    filtered_card_ids = [c for c in draft.card_ids if c in valid_card_ids]
    filtered_message_ids = [m for m in draft.message_ids if m in valid_message_ids]
    filtered_buckets: dict[str, list[uuid.UUID]] = {}
    for bucket, ids in draft.section_buckets.items():
        keep = [i for i in ids if i in valid_card_ids or i in valid_message_ids]
        filtered_buckets[bucket] = keep

    return DigestDraft(
        content_md=draft.content_md,
        card_ids=filtered_card_ids,
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
        card_ids=[],
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
) -> DigestRecord:
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

    loaded = await _load_member_profile(session, project_member_id)
    if loaded is None:
        msg = f"membership {project_member_id} not found"
        raise RuntimeError(msg)
    member, org_id = loaded

    project_id = await _resolve_project_id_for_member(
        session,
        project_member_id=project_member_id,
        org_id=org_id,
    )
    project = await _load_project_snapshot(
        session,
        phase=phase,
        project_id=project_id,
    )

    scored = await digest_repo.top_scored_items_for_member(
        session,
        project_member_id=project_member_id,
        limit=_TOP_N_SCORED,
    )
    cards = await digest_repo.open_cards_for_member_subsystems(
        session,
        project_id=project_id,
        owned_subsystems=member.owned_subsystems,
        limit=_OPEN_CARDS_LIMIT,
    )
    prior = await digest_repo.list_recent_for_member(
        session,
        project_member_id=project_member_id,
        before_day_index=day_index,
        limit=_PRIOR_DIGESTS_LIMIT,
    )

    ctx = DigestContext(
        member=member,
        project=project,
        day_index=day_index,
        top_scored_items=scored,
        open_cards=cards,
        prior_digests=prior,
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
        log.warning(
            "digest.draft_failed",
            project_member_id=str(project_member_id),
            day_index=day_index,
            error=str(exc),
        )
        raise
    except Exception as exc:  # noqa: BLE001  fall back when LLM provider is down
        log.warning(
            "digest.llm_unavailable_fallback",
            project_member_id=str(project_member_id),
            day_index=day_index,
            error=str(exc),
        )
        draft = _stub_draft_from_scored(scored)

    valid_card_ids = {c.card_id for c in cards}
    valid_message_ids = {s.message_id for s in scored}
    draft = _filter_cited_ids(
        draft,
        valid_card_ids=valid_card_ids,
        valid_message_ids=valid_message_ids,
    )

    persisted = await digest_repo.upsert_digest(
        session,
        org_id=org_id,
        project_member_id=project_member_id,
        day_index=day_index,
        phase=phase,
        content_md=draft.content_md,
        card_ids=draft.card_ids,
        message_ids=draft.message_ids,
    )
    log.info(
        "digest.generated",
        digest_id=str(persisted.id),
        project_member_id=str(project_member_id),
        day_index=day_index,
        phase=phase,
        card_count=len(draft.card_ids),
        message_count=len(draft.message_ids),
    )
    return persisted
