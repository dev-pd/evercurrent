from __future__ import annotations

from evercurrent.notify.block_kit import digest_to_blocks


def test_digest_renders_header_block() -> None:
    blocks = digest_to_blocks(
        "Some content",
        title="Day 14 · DVT · Jun 7",
    )

    assert blocks[0]["type"] == "header"
    assert blocks[0]["text"]["text"] == "Day 14 · DVT · Jun 7"
    assert blocks[1]["type"] == "divider"


def test_priority_buckets_become_section_blocks() -> None:
    digest_md = (
        "## Top priority\n"
        "- ECO-178 blocked\n"
        "- AlumWest supplier risk\n"
        "## Watch-outs\n"
        "- DVT exit slip\n"
        "## FYI\n"
        "- Lunch moved\n"
    )

    blocks = digest_to_blocks(digest_md, title="Day 14")

    section_blocks = [b for b in blocks if b["type"] == "section"]
    assert len(section_blocks) == 3
    bucket_texts = [b["text"]["text"] for b in section_blocks]
    assert any("Top priority" in t for t in bucket_texts)
    assert any("Watch-outs" in t for t in bucket_texts)
    assert any("FYI" in t for t in bucket_texts)


def test_citations_become_link_buttons() -> None:
    blocks = digest_to_blocks(
        "## Top\n- something",
        title="Day 1",
        citations=[
            {"label": "#mech 14:32", "url": "https://app/decisions/abc"},
            {"label": "#supply 09:01", "url": "https://app/decisions/def"},
        ],
    )

    actions = [b for b in blocks if b["type"] == "actions"]
    assert len(actions) == 1
    elements = actions[0]["elements"]
    assert len(elements) == 2
    assert all(el["type"] == "button" for el in elements)
    assert all("url" in el for el in elements)


def test_empty_digest_renders_safely() -> None:
    blocks = digest_to_blocks("", title="Day 1")

    assert blocks[0]["type"] == "header"
    assert blocks[1]["type"] == "divider"
    section_blocks = [b for b in blocks if b["type"] == "section"]
    assert len(section_blocks) == 1
    assert "No new activity" in section_blocks[0]["text"]["text"]


def test_long_bucket_is_truncated_under_slack_limit() -> None:
    long_body = "x" * 6000
    blocks = digest_to_blocks(
        f"## Big\n{long_body}",
        title="Day 1",
    )

    section_blocks = [b for b in blocks if b["type"] == "section"]
    assert all(len(b["text"]["text"]) <= 3000 for b in section_blocks)
