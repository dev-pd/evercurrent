from __future__ import annotations

from evercurrent.db.models.base import Base
from evercurrent.db.models.cards import Card, CardSource
from evercurrent.db.models.connectors import Connector, ConnectorChannel, RawEvent
from evercurrent.db.models.digests import Digest
from evercurrent.db.models.documents import Document, DocumentChunk
from evercurrent.db.models.messages import Message, MessageTag
from evercurrent.db.models.orgs import Org, OrgMembership
from evercurrent.db.models.projects import Channel, Project
from evercurrent.db.models.scoring import Score
from evercurrent.db.models.users import User

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
    "Message",
    "MessageTag",
    "Org",
    "OrgMembership",
    "Project",
    "RawEvent",
    "Score",
    "User",
    "metadata",
]
