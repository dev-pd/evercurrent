---
name: add-llm-prompt
description: |
  Use this skill when adding a new LLM prompt or modifying an existing one
  in the EverCurrent backend. Covers prompts for message tagging, digest
  generation, decision extraction, and agent system prompts. Covers file
  layout (prompts/*.txt), Pydantic schemas for structured output, model
  tier selection (Haiku vs Sonnet), retry logic, and observability.
---

# Add an LLM prompt

Use when adding a new prompt to any module under `apps/api/src/evercurrent/`.

## File layout

Prompts live as plain text files alongside the module that uses them:

```
apps/api/src/evercurrent/<module>/
├── __init__.py
├── <main_module>.py         e.g. tagger.py, generator.py, extractor.py
├── schemas.py               Pydantic models for prompt input/output
└── prompts/
    └── <prompt_name>.txt    The actual prompt template
```

Why text files and not Python strings?

- Easier to read and edit
- Diffs are clean
- Could be hot-reloaded in the future
- Don't pollute Python files with multi-line strings

## Prompt template format

Use `.format()` placeholders. Keep prompts short and structured:

```
# apps/api/src/evercurrent/enrichment/prompts/tag_message.txt

You analyze Slack messages from a hardware engineering team.

For each message, tag it with:
- topic: one of [{topics_list}]
- urgency: low | medium | high | critical
- affected_roles: which roles should care (from [{roles_list}])
- entities: parts, suppliers, subsystems mentioned

Messages to tag:
{messages_json}

Return a JSON array of tags, one per input message, in the same order.
Output strictly valid JSON. No prose, no markdown fences.
```

Loader pattern:

```python
from pathlib import Path
from functools import cache

PROMPTS_DIR = Path(__file__).parent / "prompts"

@cache
def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
```

Cached because prompts don't change at runtime.

## Pydantic schemas for structured output

Define the expected output shape in `<module>/schemas.py`:

```python
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field


class MessageTag(BaseModel):
    model_config = ConfigDict(strict=True)

    topic: Literal[
        "supply_chain_disruption",
        "quality_issue",
        "design_change",
        "firmware_bug",
        "test_result",
        "schedule_risk",
        "eco",
        "supplier_issue",
        "thermal",
        "mechanical",
        "electrical",
        "general_discussion",
    ]
    urgency: Literal["low", "medium", "high", "critical"]
    affected_roles: list[
        Literal["mech_eng", "ee", "supply_chain", "pm", "qa", "firmware"]
    ]
    entities: Annotated[list[str], Field(max_length=20)]
```

## Tier selection

Use `claude-haiku-4-5-20251001` for high-volume, lower-stakes tasks.
Use `claude-sonnet-4-6` for high-stakes generation and reasoning.

| Task | Model |
|---|---|
| Message tagging | Haiku |
| Synthetic data generation (per-day) | Haiku for messages, Sonnet for docs |
| Digest generation | Sonnet |
| Decision extraction | Sonnet |
| Agent (tool-use loop) | Sonnet |
| RAG retrieval embeddings | Voyage `voyage-3-lite` (not Claude) |

Wire via `llm/tiering.py`:

```python
from evercurrent.llm.client import LLMProvider

async def tag_message(provider: LLMProvider, messages: list[Message]) -> list[MessageTag]:
    prompt = load_prompt("tag_message").format(
        topics_list=", ".join(TOPIC_VALUES),
        roles_list=", ".join(ROLE_VALUES),
        messages_json=json_dumps_for_prompt(messages),
    )
    raw = await provider.complete(
        model="claude-haiku-4-5-20251001",
        prompt=prompt,
        max_tokens=2048,
        response_schema=list[MessageTag],
    )
    return raw
```

The `LLMProvider.complete` wrapper handles JSON parsing, validation, retry.

## Structured output strategy

Use Anthropic's tool-use mechanism for structured output (more reliable
than JSON-mode prompting):

1. Define the output schema as a Pydantic model.
2. Convert to JSON Schema via `Model.model_json_schema()`.
3. Pass as a "tool" the model is instructed to call.
4. Parse the tool_use response back into the Pydantic model.

The `llm/client.py` wrapper abstracts this. Just pass `response_schema=`
and get back validated Pydantic instances.

If schema-as-tool doesn't fit (rare), fall back to JSON-mode prompting:

- Add `"Return strictly valid JSON. No prose, no markdown fences."` to
  the prompt.
- Strip ```json fences if present before parsing.
- Validate with the Pydantic model. On `ValidationError`, log and retry
  once with the error message appended to the prompt.

## Retry and error handling

Inside `LLMProvider.complete`:

- Transient errors (429, 500, 502, 503, 504, network errors): retry with
  exponential backoff via tenacity, up to 3 attempts.
- ValidationError on structured output: one retry with the error message
  appended to the prompt as a correction hint.
- Non-recoverable errors (401, 403): raise immediately.

## Observability

Every LLM call logs:

```python
log.info(
    "llm.call",
    model=model,
    prompt_name=prompt_name,
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens,
    latency_ms=int((time.perf_counter() - start) * 1000),
)
```

This is critical for cost monitoring and debugging. The `llm/client.py`
wrapper handles this for every call.

## Prompt iteration workflow

When iterating on a prompt:

1. Add a few-shot example block if the task is ambiguous.
2. Be explicit about output format ("Return JSON. No prose.").
3. Include negative examples ("Do NOT include items where urgency is
   unclear; skip them.").
4. Test against the eval harness (`make eval`) to confirm the change
   didn't regress quality.
5. If structured output validation fails repeatedly, the prompt is
   ambiguous about the schema. Add constraints in the prompt itself
   (max lengths, allowed values).

## Prompt review checklist

- [ ] Lives in `<module>/prompts/<name>.txt`
- [ ] Has placeholders (`{name}`) for runtime values
- [ ] Output schema defined in `<module>/schemas.py`
- [ ] Loaded via cached `load_prompt()` helper
- [ ] Uses appropriate tier (Haiku vs Sonnet)
- [ ] Has structured output (schema-as-tool, not free text)
- [ ] Logs token usage
- [ ] Has retry logic for transient and validation errors

## Common mistakes

- Inline multi-line strings in Python code instead of `.txt` files.
- Free-text outputs requiring regex parsing. Use structured output.
- No max length on list outputs (Pydantic `Field(max_length=N)`).
- Forgetting to log token usage.
- Using Sonnet for tagging (10x cost for no quality gain).
- Using Haiku for the agent's reasoning loop (quality degrades).
