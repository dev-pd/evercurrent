"""Eval-suite fixtures + lightweight terminal reporting.

Per the project's testing policy (AGENTS.md §11) these are NOT
correctness unit tests; they emit metrics that we track in
docs/EVAL_BASELINE.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def scoring_scenarios() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "scoring_scenarios.json").read_text())


@pytest.fixture(scope="session")
def decision_truth() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "decision_truth.json").read_text())


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
