"""Connector framework.

Each external data source (Slack today, Drive in Phase 10, ...) lives
in its own subpackage under `connectors/`. Every subpackage implements
the `Connector` protocol from `base.py` so the rest of the app can
treat them uniformly: install, list channels, ingest events, backfill.
"""

from __future__ import annotations

from evercurrent.connectors.base import Connector

__all__ = ["Connector"]
