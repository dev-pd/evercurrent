"""SQLAlchemy 2.0 async DB layer.

`models` exposes the declarative ORM classes. `session` provides the
async session factory and FastAPI lifespan helpers. Repositories under
`repositories/` translate domain models to/from SQLAlchemy models.
"""

from evercurrent.db.models import Base

__all__ = ["Base"]
