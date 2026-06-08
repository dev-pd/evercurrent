"""Digest markdown → Slack Block Kit blocks.

Pure mapping. We parse a light markdown structure (`## Bucket name`
headings + bullet lines) and emit a header block, a divider, one
section block per bucket, and a citations actions row of link buttons.

Slack hard limits a single text block to 3000 chars, so each bucket's
combined body is truncated with a tail-out link to the full Card in the
web app.
"""

from __future__ import annotations

import re
from typing import Any

_BLOCK_TEXT_LIMIT = 3000
_HEADING_RE = re.compile(r"^\s*#{1,3}\s+(?P<title>.+?)\s*$")


def _truncate(text: str, *, limit: int = _BLOCK_TEXT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit - 64].rstrip()
    return f"{head}\n\n_...truncated; open the dashboard for the full digest._"


def _split_buckets(digest_md: str) -> list[tuple[str, str]]:
    """Yield (bucket_title, body_markdown) tuples.

    Lines before any heading become an implicit "Highlights" bucket so
    we always render something even when the digest agent skips section
    headers.
    """
    buckets: list[tuple[str, list[str]]] = []
    current_title = "Highlights"
    current_body: list[str] = []
    for raw_line in digest_md.splitlines():
        match = _HEADING_RE.match(raw_line)
        if match is not None:
            if current_body or buckets:
                buckets.append((current_title, current_body))
            current_title = match.group("title").strip()
            current_body = []
            continue
        current_body.append(raw_line)
    if current_body or not buckets:
        buckets.append((current_title, current_body))
    return [
        (title, "\n".join(body).strip())
        for title, body in buckets
        if "\n".join(body).strip() or title != "Highlights"
    ]


def digest_to_blocks(
    digest_md: str,
    *,
    title: str,
    citations: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Translate a digest markdown body into Block Kit blocks.

    Args:
        digest_md: the markdown body produced by the digest agent.
        title: header text, e.g. `"Day 14 · DVT · Jun 7"`.
        citations: optional `[{"label": "#mech-design 14:32", "url": ...}]`
            entries rendered as a single actions row of link buttons.

    Returns a Block Kit `blocks` list ready for `chat.postMessage`.
    """
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": title[:150], "emoji": True},
        },
        {"type": "divider"},
    ]

    body = digest_md.strip()
    if not body:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No new activity to surface today._",
                },
            },
        )
    else:
        for bucket_title, bucket_body in _split_buckets(body):
            text = f"*{bucket_title}*"
            if bucket_body:
                text = f"{text}\n{bucket_body}"
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": _truncate(text)},
                },
            )

    if citations:
        elements: list[dict[str, Any]] = []
        for cite in citations:
            label = (cite.get("label") or "View").strip()[:75]
            url = cite.get("url")
            if not url:
                continue
            elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": label, "emoji": True},
                    "url": url,
                },
            )
        if elements:
            blocks.append({"type": "actions", "elements": elements})

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "Reply with feedback or thumbs up to retrain your digest."
                    ),
                },
            ],
        },
    )
    return blocks
