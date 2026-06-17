from __future__ import annotations

import json
import uuid
from importlib import resources
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.cards import repository as cards_repo
from evercurrent.cards.schemas import CardDraft
from evercurrent.db.repositories.messages import MessageRepository
from evercurrent.llm.client import LLMProvider
from evercurrent.llm.tiering import ModelTier
from evercurrent.mcp.client import InProcessMCPClient
from evercurrent.mcp.schemas import ThreadContext

log = structlog.get_logger(__name__)


_PROMPT_PKG = "evercurrent.cards.prompts"


def _load_prompt(name: str) -> str:
    return resources.files(_PROMPT_PKG).joinpath(name).read_text(encoding="utf-8")


_RETRY_REMINDER = (
    "Your previous response did not match the CardDraft schema. "
    "Re-emit as a single JSON object with exactly these fields: "
    "summary (string, 10..200 chars), body (string, >=20 chars), "
    "affected_subsystems (array of strings, 0..3 entries), "
    "confidence (number 0..1), decided_at (ISO-8601 string or null)."
)


async def _load_message_meta(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> dict[str, Any] | None:
    return await MessageRepository(session).get(message_id)


def _format_thread_block(
    *,
    own_text: str,
    own_author: str,
    thread: ThreadContext | None,
) -> str:
    if thread is None:
        return f"Trigger message from {own_author}:\n{own_text}"
    lines: list[str] = [
        f"Thread root by {thread.root.author}:",
        thread.root.text,
    ]
    for reply in thread.replies:
        lines.append(f"\nReply by {reply.author}:")
        lines.append(reply.text)
    return "\n".join(lines)


def _build_prompt(
    *,
    kind: str,
    summary_hint: str,
    thread_block: str,
    project_phase: str,
    known_subsystems: list[str],
) -> tuple[str, str]:
    system = _load_prompt("draft_card.txt")
    subsystems_block = ", ".join(known_subsystems) if known_subsystems else "(no fixed vocabulary)"
    user = (
        f"Kind: {kind}\n"
        f"Project phase: {project_phase}\n"
        f"Known subsystems: {subsystems_block}\n"
        f"Router summary hint: {summary_hint}\n\n"
        f"Context:\n{thread_block}\n\n"
        f"Draft the Card. Return JSON only."
    )
    return system, user


async def _complete_json(
    llm: LLMProvider,
    *,
    system: str,
    prompt: str,
) -> dict[str, Any] | list[Any]:
    return await llm.complete_json(
        tier=ModelTier.DOC_GEN,
        system=system,
        prompt=prompt,
        max_tokens=1024,
        temperature=0.2,
    )


def _parse_draft(payload: Any) -> CardDraft:
    if isinstance(payload, list):
        msg = "expected JSON object, got list"
        raise TypeError(msg)
    return CardDraft.model_validate(payload)


async def _draft_with_retry(
    llm: LLMProvider,
    *,
    system: str,
    prompt: str,
) -> CardDraft:
    try:
        payload = await _complete_json(llm, system=system, prompt=prompt)
        return _parse_draft(payload)
    except (ValidationError, json.JSONDecodeError, ValueError, TypeError) as first_exc:
        log.warning(
            "cards.draft.retry",
            reason="schema_drift",
            error=str(first_exc),
        )

    retry_prompt = prompt + "\n\n" + _RETRY_REMINDER
    payload = await _complete_json(llm, system=system, prompt=retry_prompt)
    return _parse_draft(payload)


async def _resolve_project_context(
    session: AsyncSession,
    project_id: uuid.UUID | None,
) -> tuple[str, list[str]]:
    if project_id is None:
        return "unknown", []
    row = (
        await session.execute(
            text(
                "SELECT current_phase, phase_concerns FROM projects WHERE id = :id",
            ),
            {"id": str(project_id)},
        )
    ).first()
    if row is None:
        return "unknown", []
    phase = str(row[0] or "unknown")
    concerns = row[1] or {}
    subsystems = list(concerns.get("subsystems") or []) if isinstance(concerns, dict) else []
    return phase, [str(s) for s in subsystems]


def _existing_to_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "card_id": uuid.UUID(str(row["id"])),
        "org_id": uuid.UUID(str(row["org_id"])),
        "project_id": uuid.UUID(str(row["project_id"])) if row["project_id"] else None,
        "summary": str(row["summary"]),
        "kind": str(row["kind"]),
        "existing": True,
    }


async def build_card(
    session: AsyncSession,
    llm: LLMProvider,
    *,
    message_id: uuid.UUID,
    kind: str,
    summary_hint: str,
    mcp_client: InProcessMCPClient | None = None,
) -> dict[str, Any]:
    existing = await cards_repo.get_existing_card(
        session,
        triggering_message_id=message_id,
        kind=kind,
    )
    if existing is not None:
        log.info(
            "cards.idempotent_hit",
            card_id=str(existing["id"]),
            message_id=str(message_id),
            kind=kind,
        )
        return _existing_to_response(existing)

    meta = await _load_message_meta(session, message_id)
    if meta is None:
        msg = f"message {message_id} not found"
        raise RuntimeError(msg)

    org_id = uuid.UUID(str(meta["org_id"]))
    project_id = uuid.UUID(str(meta["project_id"])) if meta["project_id"] else None

    client = mcp_client or InProcessMCPClient()
    thread = await client.call(
        "get_thread_context",
        session,
        {"message_id": message_id},
    )

    thread_block = _format_thread_block(
        own_text=str(meta["text"] or ""),
        own_author=str(meta["author_display_name"] or "unknown"),
        thread=thread if isinstance(thread, ThreadContext) else None,
    )
    project_phase, known_subsystems = await _resolve_project_context(
        session,
        project_id,
    )
    system, prompt = _build_prompt(
        kind=kind,
        summary_hint=summary_hint,
        thread_block=thread_block,
        project_phase=project_phase,
        known_subsystems=known_subsystems,
    )

    try:
        draft = await _draft_with_retry(llm, system=system, prompt=prompt)
    except (ValidationError, json.JSONDecodeError, ValueError, TypeError) as exc:
        log.warning(
            "cards.draft.failed",
            message_id=str(message_id),
            kind=kind,
            error=str(exc),
        )
        raise

    try:
        card_id = await cards_repo.insert_card(
            session,
            org_id=org_id,
            project_id=project_id,
            kind=kind,
            summary=draft.summary,
            body=draft.body,
            affected_subsystems=draft.affected_subsystems,
            confidence=draft.confidence,
            decided_at=draft.decided_at if kind == "decision" else None,
            triggering_message_id=message_id,
        )
    except IntegrityError:
        await session.rollback()
        existing = await cards_repo.get_existing_card(
            session,
            triggering_message_id=message_id,
            kind=kind,
        )
        if existing is None:
            raise
        log.info(
            "cards.idempotent_hit",
            card_id=str(existing["id"]),
            message_id=str(message_id),
            kind=kind,
            race=True,
        )
        return _existing_to_response(existing)

    refs: list[tuple[str, uuid.UUID]] = [("message", message_id)]
    if isinstance(thread, ThreadContext):
        if thread.root.id != message_id:
            refs.append(("message", thread.root.id))
        refs.extend(("message", reply.id) for reply in thread.replies if reply.id != message_id)

    await cards_repo.add_card_sources(
        session,
        org_id=org_id,
        card_id=card_id,
        refs=refs,
    )

    log.info(
        "cards.build",
        card_id=str(card_id),
        message_id=str(message_id),
        kind=kind,
        confidence=draft.confidence,
        sources=len(refs),
    )

    return {
        "card_id": card_id,
        "org_id": org_id,
        "project_id": project_id,
        "summary": draft.summary,
        "kind": kind,
        "existing": False,
    }
