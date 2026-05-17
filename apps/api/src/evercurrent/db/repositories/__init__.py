"""Repositories: thin async data-access layer mapping ORM ↔ domain models.

Repositories take an `AsyncSession` parameter and never own the session
lifecycle. They take and return pure domain models, never SQLAlchemy
models. Each module owns one aggregate root.
"""

from evercurrent.db.repositories.channels import ChannelRepository
from evercurrent.db.repositories.decisions import DecisionRepository
from evercurrent.db.repositories.digests import DigestRepository
from evercurrent.db.repositories.documents import DocumentRepository
from evercurrent.db.repositories.feedback import FeedbackRepository
from evercurrent.db.repositories.messages import MessageRepository
from evercurrent.db.repositories.projects import ProjectRepository
from evercurrent.db.repositories.users import UserRepository

__all__ = [
    "ChannelRepository",
    "DecisionRepository",
    "DigestRepository",
    "DocumentRepository",
    "FeedbackRepository",
    "MessageRepository",
    "ProjectRepository",
    "UserRepository",
]
