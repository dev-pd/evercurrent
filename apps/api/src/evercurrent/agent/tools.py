"""Tool definitions + handlers for the EverCurrent agent."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

import structlog

from evercurrent.db.repositories import (
    DecisionRepository,
    MessageRepository,
    ProjectRepository,
    UserRepository,
)
from evercurrent.db.session import session_scope
from evercurrent.domain.decisions import DecisionStatus
from evercurrent.llm.client import ToolSpec
from evercurrent.rag.retriever import search_documents as rag_search

log = structlog.get_logger(__name__)

_DEFAULT_MESSAGE_LIMIT = 10
_DEFAULT_RAG_TOP_K = 5
_DEFAULT_DECISION_LIMIT = 25


@dataclass(frozen=True, slots=True)
class ToolContext:
    project_id: uuid.UUID
    user_id: uuid.UUID | None = None


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="search_messages",
        description=(
            "Full-text search Slack-style team messages. Supports filters by "
            "channel (e.g. '#mech-design'), author username, topic, since "
            "(ISO datetime). Returns at most `limit` messages with their tags."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to search for."},
                "channel": {"type": "string"},
                "author": {"type": "string"},
                "since": {"type": "string", "description": "ISO 8601 datetime."},
                "topic": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="get_thread_context",
        description="Return the full thread (root + replies) for a message id.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "UUID of root or reply."},
            },
            "required": ["message_id"],
        },
    ),
    ToolSpec(
        name="get_user_context",
        description=(
            "Return role, owned subsystems/parts, and learned topic weights "
            "for a user. Use to personalise an answer when the user_id is "
            "available in conversation context."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "UUID."},
            },
            "required": ["user_id"],
        },
    ),
    ToolSpec(
        name="get_project_state",
        description=(
            "Return the project's current phase, current_day, phase_concerns "
            "map, and milestones. No arguments — operates on the current "
            "project."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="search_documents",
        description=(
            "Semantic search over project documents (PRD, BOM, ECO log, test "
            "reports). Filter by kind list when you already know the doc "
            "type. Returns top_k chunks with section_path and similarity."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "document_kinds": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional. e.g. ['prd','bom','eco_log'].",
                },
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="query_decisions",
        description=(
            "List structured decisions for the current project. Optional "
            "filters: since (ISO datetime), status (proposed | decided | "
            "implemented | reverted), limit."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "since": {"type": "string"},
                "status": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
        },
    ),
]


# ----- handlers ---------------------------------------------------------------


def _parse_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed


async def _search_messages(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    async with session_scope() as session:
        repo = MessageRepository(session)
        results = await repo.search_text(
            ctx.project_id,
            query=str(args.get("query", "")),
            channel_name=args.get("channel"),
            author_username=args.get("author"),
            topic=args.get("topic"),
            since=_parse_dt(args.get("since")),
            limit=int(args.get("limit", _DEFAULT_MESSAGE_LIMIT)),
        )
    return {
        "results": [
            {
                "id": str(em.message.id),
                "channel": em.channel_name,
                "author": em.author_username,
                "ts": em.message.ts.isoformat(),
                "day": em.message.day,
                "text": em.message.text,
                "topic": em.tag.topic if em.tag else None,
                "urgency": em.tag.urgency.value if em.tag else None,
            }
            for em in results
        ],
    }


async def _get_thread_context(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
    raw = args.get("message_id")
    if not raw:
        return {"error": "message_id is required"}
    try:
        message_id = uuid.UUID(str(raw))
    except ValueError:
        return {"error": "invalid message_id"}
    async with session_scope() as session:
        repo = MessageRepository(session)
        enriched = await repo.get_enriched(message_id)
        if enriched is None:
            return {"error": "message not found"}
        root_id = enriched.message.thread_root_id or enriched.message.id
        thread = await repo.get_thread(root_id)
    return {
        "root_id": str(root_id),
        "thread": [
            {
                "id": str(m.id),
                "author_id": str(m.author_id),
                "ts": m.ts.isoformat(),
                "text": m.text,
            }
            for m in thread
        ],
    }


async def _get_user_context(args: dict[str, Any], _ctx: ToolContext) -> dict[str, Any]:
    raw = args.get("user_id")
    if not raw:
        return {"error": "user_id is required"}
    try:
        user_id = uuid.UUID(str(raw))
    except ValueError:
        return {"error": "invalid user_id"}
    async with session_scope() as session:
        user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        return {"error": "user not found"}
    return {
        "id": str(user.id),
        "display_name": user.display_name,
        "role": user.role.value,
        "owned_subsystems": user.owned_subsystems,
        "owned_parts": user.owned_parts,
        "topic_weights": user.topic_weights,
    }


async def _get_project_state(_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    async with session_scope() as session:
        project = await ProjectRepository(session).get_by_id(ctx.project_id)
    if project is None:
        return {"error": "project not found"}
    return {
        "id": str(project.id),
        "name": project.name,
        "current_phase": project.current_phase,
        "current_day": project.current_day,
        "phase_concerns": project.phase_concerns,
        "milestones": project.milestones,
    }


async def _search_documents(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    results = await rag_search(
        query=str(args.get("query", "")),
        project_id=ctx.project_id,
        document_kinds=args.get("document_kinds"),
        top_k=int(args.get("top_k", _DEFAULT_RAG_TOP_K)),
    )
    return {
        "results": [
            {
                "document_title": r.document_title,
                "document_kind": r.document_kind,
                "section_path": r.section_path,
                "text": r.text,
                "similarity": round(r.similarity, 4),
            }
            for r in results
        ],
    }


async def _query_decisions(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    status_value = args.get("status")
    status: DecisionStatus | None = None
    if status_value:
        try:
            status = DecisionStatus(str(status_value))
        except ValueError:
            return {"error": f"unknown status {status_value!r}"}
    async with session_scope() as session:
        decisions = await DecisionRepository(session).list_for_project(
            ctx.project_id,
            since=_parse_dt(args.get("since")),
            status=status,
            limit=int(args.get("limit", _DEFAULT_DECISION_LIMIT)),
        )
    return {
        "decisions": [
            {
                "id": str(d.id),
                "summary": d.summary,
                "rationale": d.rationale,
                "decided_by": d.decided_by,
                "decided_at": d.decided_at.isoformat(),
                "affected_subsystems": d.affected_subsystems,
                "source_message_ids": [str(m) for m in d.source_message_ids],
                "status": d.status.value,
                "confidence": d.confidence,
            }
            for d in decisions
        ],
    }


HANDLERS: dict[str, Any] = {
    "search_messages": _search_messages,
    "get_thread_context": _get_thread_context,
    "get_user_context": _get_user_context,
    "get_project_state": _get_project_state,
    "search_documents": _search_documents,
    "query_decisions": _query_decisions,
}


async def dispatch_tool(
    name: str,
    args: dict[str, Any],
    ctx: ToolContext,
) -> dict[str, Any]:
    """Run a tool by name. Returns the tool result payload."""
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool {name!r}"}
    try:
        result = await handler(args, ctx)
    except Exception as exc:
        log.exception("agent.tool.error", tool=name)
        return {"error": f"{type(exc).__name__}: {exc}"}
    return result
