"""Eval harness.

Four scripts (router / scoring / rag / digest) that produce reference
numbers tracked in `docs/EVAL_BASELINE.md`. Per the testing philosophy
in `AGENTS.md` these are NOT correctness unit tests — they emit
metrics. A baseline miss logs a warning but does not fail CI.
"""
