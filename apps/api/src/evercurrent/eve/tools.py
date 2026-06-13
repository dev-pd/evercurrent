"""Tool specs Eve exposes to the model.

READ_TOOLS are thin wrappers over the in-process MCP read tools (project_id is
injected server-side, never by the LLM). EMIT_TOOL is the structured terminal
action whose schema mirrors `ProactiveInsight`.
"""

from __future__ import annotations

from evercurrent.llm.client import ToolSpec

READ_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="search_messages",
        description="Semantic search over Slack messages. Returns relevant message snippets.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "what to look for"}},
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="search_documents",
        description="Semantic search over spec/BOM/requirement PDFs. The formal source of truth.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="query_cards",
        description="List extracted decisions/risks. Optional kind=decision|risk, status=open.",
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "status": {"type": "string"},
            },
        },
    ),
]

EMIT_TOOL = ToolSpec(
    name="emit_insight",
    description="Emit the final structured insight. Call this once when you have evidence.",
    input_schema={
        "type": "object",
        "properties": {
            "req_id": {"type": "string", "description": "e.g. REQ-245 or a short id"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "affected_subsystems": {"type": "array", "items": {"type": "string"}},
            "before": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"label": {"type": "string"}, "value": {"type": "string"}},
                },
            },
            "after": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"label": {"type": "string"}, "value": {"type": "string"}},
                },
            },
            "conflicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "subsystem": {"type": "string"},
                        "severity": {"type": "string", "enum": ["info", "warn", "critical"]},
                        "title": {"type": "string"},
                        "detail": {"type": "string"},
                        "impact": {"type": "string"},
                    },
                },
            },
            "sources": {
                "type": "array",
                "minItems": 2,
                "description": "Real evidence you used: at least two Slack snippets or cards.",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["slack", "doc"]},
                        "channel": {"type": "string"},
                        "author": {"type": "string"},
                        "snippet": {"type": "string"},
                    },
                    "required": ["kind", "snippet"],
                },
            },
            "impact_summary": {
                "type": "object",
                "properties": {
                    "cost": {"type": "string"},
                    "schedule": {"type": "string"},
                    "revenue_at_risk": {"type": "string"},
                },
            },
            "suggested_action": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "invitees": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                },
            },
        },
        "required": [
            "title",
            "summary",
            "affected_subsystems",
            "conflicts",
            "sources",
            "suggested_action",
        ],
    },
)
