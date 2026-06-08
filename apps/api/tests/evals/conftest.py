"""Eval-suite fixtures, gating, and report-writing.

Per `AGENTS.md` §11 the evals are NOT correctness gates — they emit
metrics. The fixtures here:

1. Load hand-labelled JSON datasets from `data/`.
2. Gate on `ANTHROPIC_API_KEY` / `VOYAGE_API_KEY` env vars. If missing,
   the LLM/embedding evals skip with a clear reason instead of failing
   with a 401 deep in a request.
3. Provide an `AnthropicProvider` factory bound to the real client when
   a key is present.
4. Persist run reports to `tests/evals/reports/<isoformat>.json` so we
   can track baselines over time.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

import pytest

from evercurrent.llm.client import AnthropicProvider, LLMProvider

# Collect `eval_*.py` files in this directory the same way pytest collects
# `test_*.py` elsewhere. The project-wide pytest config only matches
# `test_*.py`; this hook adds eval_ files without touching pyproject.toml.
collect_ignore_glob: list[str] = []


def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> pytest.Collector | None:
    if file_path.suffix != ".py" or not file_path.name.startswith("eval_"):
        return None
    return pytest.Module.from_parent(parent, path=file_path)

DATA_DIR = Path(__file__).parent / "data"
JUDGE_PROMPTS_DIR = Path(__file__).parent / "judge_prompts"
REPORTS_DIR = Path(__file__).parent / "reports"


# ----- gating ----------------------------------------------------------------


def _have_anthropic_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _have_voyage_key() -> bool:
    return bool(os.environ.get("VOYAGE_API_KEY"))


@pytest.fixture(scope="session")
def anthropic_available() -> bool:
    return _have_anthropic_key()


@pytest.fixture(scope="session")
def voyage_available() -> bool:
    return _have_voyage_key()


@pytest.fixture(scope="session")
def llm_provider(anthropic_available: bool) -> LLMProvider:
    if not anthropic_available:
        pytest.skip("ANTHROPIC_API_KEY not set; LLM eval skipped.")
    return AnthropicProvider()


# ----- data loaders ----------------------------------------------------------


def _load_json(name: str) -> list[dict[str, Any]]:
    path = DATA_DIR / name
    if not path.exists():
        msg = f"eval dataset {name} not found at {path}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def router_labels() -> list[dict[str, Any]]:
    return _load_json("router_labels.json")


@pytest.fixture(scope="session")
def scoring_scenarios() -> list[dict[str, Any]]:
    return _load_json("scoring_scenarios.json")


@pytest.fixture(scope="session")
def rag_questions() -> list[dict[str, Any]]:
    return _load_json("rag_questions.json")


@pytest.fixture(scope="session")
def digest_scenarios() -> list[dict[str, Any]]:
    return _load_json("digest_scenarios.json")


@pytest.fixture(scope="session")
def digest_judge_prompt() -> str:
    path = JUDGE_PROMPTS_DIR / "digest_rubric.txt"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def rag_corpus_dir() -> Path:
    return DATA_DIR / "rag_corpus"


# ----- reporting -------------------------------------------------------------


def write_report(name: str, report: dict[str, Any]) -> Path:
    """Persist a single eval's results to `reports/<isoformat>_<name>.json`.

    Returns the path for tests to log. We never fail the test on a write
    failure; the metric is the deliverable, the file is convenience.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    path = REPORTS_DIR / f"{stamp}_{name}.json"
    payload = {
        "name": name,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        **report,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


# ----- terminal table reporter ----------------------------------------------


def emit_metric_table(title: str, rows: list[tuple[str, ...]]) -> None:
    """Pretty-print a metric table. Captured by pytest -s in `make eval`."""
    if not rows:
        print(f"\n{title}: (no data)")
        return
    widths = [max(len(str(cell)) for cell in column) for column in zip(*rows, strict=False)]
    line = "  ".join(str(cell).ljust(width) for cell, width in zip(rows[0], widths, strict=False))
    print(f"\n=== {title} ===")
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in rows[1:]:
        print("  ".join(str(cell).ljust(w) for cell, w in zip(row, widths, strict=False)))


# ----- shared collection -----------------------------------------------------


# Evals that need a DB spin up their own testcontainer (see eval_rag.py).
# We deliberately do not share the project's top-level fixtures so a
# developer can `pytest tests/evals` without the integration DB stack.
