"""SQLAlchemy 2.0 declarative ORM models for EverCurrent.

Split by domain into one module per area; this package re-exports every model
so callers keep importing from `evercurrent.db.models`. Importing this package
registers all mappers (needed before relationship resolution / Alembic
autogenerate).
"""

from __future__ import annotations

from evercurrent.db.models.base import Base
from evercurrent.db.models.cards import Card, CardSource
from evercurrent.db.models.connectors import Connector, ConnectorChannel, RawEvent
from evercurrent.db.models.digests import Digest, Feedback
from evercurrent.db.models.documents import Document, DocumentChunk
from evercurrent.db.models.messages import Message, MessageTag
from evercurrent.db.models.notifications import Notification, Subscription
from evercurrent.db.models.orgs import Org, OrgMembership
from evercurrent.db.models.projects import Channel, Project
from evercurrent.db.models.scoring import Score
from evercurrent.db.models.users import User

# Used by Alembic via target_metadata.
metadata = Base.metadata

__all__ = [
    "Base",
    "Card",
    "CardSource",
    "Channel",
    "Connector",
    "ConnectorChannel",
    "Digest",
    "Document",
    "DocumentChunk",
    "Feedback",
    "Message",
    "MessageTag",
    "Notification",
    "Org",
    "OrgMembership",
    "Project",
    "RawEvent",
    "Score",
    "Subscription",
    "User",
    "metadata",
]
