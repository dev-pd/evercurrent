"""Drafts a decision/risk/question signal from a triggering message: pulls the
thread context, prompts Sonnet for a SignalDraft, and persists it idempotently."""

from __future__ import annotations

import json
import uuid
from importlib import resources
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.agent_tools.client import InProcessToolClient
from evercurrent.agent_tools.schemas import ThreadContext
from evercurrent.db.repositories.messages import MessageRepository
from evercurrent.llm.client import LLMProvider
from evercurrent.llm.tiering import ModelTier
from evercurrent.signals import repository as signals_repo
from evercurrent.signals.schemas import SignalDraft

log = structlog.get_logger(__name__)


_PROMPT_PKG = "evercurrent.signals.prompts"


def _load_prompt(name: str) -> str:
    return resources.files(_PROMPT_PKG).joinpath(name).read_text(encoding="utf-8")


_RETRY_REMINDER = (
    "Your previous response did not match the SignalDraft schema. "
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
    system = _load_prompt("draft_signal.txt")
    subsystems_block = ", ".join(known_subsystems) if known_subsystems else "(no fixed vocabulary)"
    user = (
        f"Kind: {kind}\n"
        f"Project phase: {project_phase}\n"
        f"Known subsystems: {subsystems_block}\n"
        f"Router summary hint: {summary_hint}\n\n"
        f"Context:\n{thread_block}\n\n"
        f"Draft the Signal. Return JSON only."
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


def _parse_draft(payload: Any) -> SignalDraft:
    if isinstance(payload, list):
        msg = "expected JSON object, got list"
        raise TypeError(msg)
    return SignalDraft.model_validate(payload)


async def _draft_with_retry(
    llm: LLMProvider,
    *,
    system: str,
    prompt: str,
) -> SignalDraft:
    try:
        payload = await _complete_json(llm, system=system, prompt=prompt)
        return _parse_draft(payload)
    except (ValidationError, json.JSONDecodeError, ValueError, TypeError) as first_exc:
        log.warning(
            "signals.draft.retry",
            reason="schema_drift",
            error=str(first_exc),
        )

    retry_prompt = prompt + "\n\n" + _RETRY_REMINDER
    payload = await _complete_json(llm, system=system, prompt=retry_prompt)
    return _parse_draft(payload)


def _existing_to_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": uuid.UUID(str(row["id"])),
        "org_id": uuid.UUID(str(row["org_id"])),
        "project_id": uuid.UUID(str(row["project_id"])) if row["project_id"] else None,
        "summary": str(row["summary"]),
        "kind": str(row["kind"]),
        "existing": True,
    }


async def build_signal(
    session: AsyncSession,
    llm: LLMProvider,
    *,
    message_id: uuid.UUID,
    kind: str,
    summary_hint: str,
    tool_client: InProcessToolClient | None = None,
) -> dict[str, Any]:
    existing = await signals_repo.get_existing_signal(
        session,
        triggering_message_id=message_id,
        kind=kind,
    )
    if existing is not None:
        log.info(
            "signals.idempotent_hit",
            signal_id=str(existing["id"]),
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

    client = tool_client or InProcessToolClient()
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
    project_phase, known_subsystems = await signals_repo.project_phase_and_subsystems(
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
            "signals.draft.failed",
            message_id=str(message_id),
            kind=kind,
            error=str(exc),
        )
        raise

    affected_roles = await signals_repo.message_affected_roles(session, message_id)
    try:
        signal_id = await signals_repo.insert_signal(
            session,
            org_id=org_id,
            project_id=project_id,
            kind=kind,
            summary=draft.summary,
            body=draft.body,
            affected_subsystems=draft.affected_subsystems,
            affected_roles=affected_roles,
            confidence=draft.confidence,
            decided_at=draft.decided_at if kind == "decision" else None,
            triggering_message_id=message_id,
        )
    except IntegrityError:
        await session.rollback()
        existing = await signals_repo.get_existing_signal(
            session,
            triggering_message_id=message_id,
            kind=kind,
        )
        if existing is None:
            raise
        log.info(
            "signals.idempotent_hit",
            signal_id=str(existing["id"]),
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

    await signals_repo.add_signal_sources(
        session,
        org_id=org_id,
        signal_id=signal_id,
        refs=refs,
    )

    log.info(
        "signals.build",
        signal_id=str(signal_id),
        message_id=str(message_id),
        kind=kind,
        confidence=draft.confidence,
        sources=len(refs),
    )

    return {
        "signal_id": signal_id,
        "org_id": org_id,
        "project_id": project_id,
        "summary": draft.summary,
        "kind": kind,
        "existing": False,
    }
