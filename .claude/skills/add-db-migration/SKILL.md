---
name: add-db-migration
description: |
  Use this skill when adding, modifying, or removing database tables and
  columns in the EverCurrent backend. Covers Alembic migration creation,
  the autogenerate workflow, pgvector-specific concerns, indexes, and the
  rules about never editing merged migrations.
---

# Add a database migration

Use when any DB schema change is needed (new table, new column, new index,
constraint change, etc.).

## The flow

1. Edit SQLAlchemy models in `apps/api/src/evercurrent/db/models.py`.
2. Generate a migration: `cd apps/api && uv run alembic revision --autogenerate -m "short description"`.
3. Review the generated migration carefully. Autogenerate is good, not
   perfect.
4. Test by running `uv run alembic upgrade head` against a fresh DB.
5. Test downgrade: `uv run alembic downgrade -1`, then `upgrade head` again.
6. Commit the model change and migration file together.

## Naming

Migration files are named by Alembic: `<rev_id>_<slug>.py`. The slug comes
from your `-m` message. Use a short, action-oriented description:

```
✓ "add ECO log entity table"
✓ "add HNSW index on document_chunks"
✓ "add status column to decisions"
✗ "wip"
✗ "schema update"
✗ "fix"
```

## What autogenerate handles well

- New tables (from new SQLAlchemy models)
- New columns
- Removed columns
- Type changes (mostly)
- Indexes declared on Mapped columns

## What autogenerate does NOT handle (you have to hand-write)

- `CREATE EXTENSION vector;` for pgvector. Initial migration must include:
  ```python
  def upgrade() -> None:
      op.execute("CREATE EXTENSION IF NOT EXISTS vector")
      # ... table creation ...
  ```
- HNSW or other vector indexes:
  ```python
  op.execute(
      "CREATE INDEX document_chunks_embedding_hnsw "
      "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
  )
  ```
- GIN indexes on JSONB columns:
  ```python
  op.execute(
      "CREATE INDEX document_chunks_metadata_gin "
      "ON document_chunks USING gin (metadata)"
  )
  ```
- Triggers, stored procedures, advanced constraints
- Data migrations (moving data between columns/tables)

Always check the generated file and add these by hand if missing.

## pgvector column declaration in SQLAlchemy

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # ... other columns ...
    embedding: Mapped[list[float]] = mapped_column(Vector(512))
```

Vector dim 512 because we use Voyage `voyage-3-lite`. Locked.

## UUID primary keys

Every table gets:

```python
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

class MyTable(Base):
    __tablename__ = "my_table"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
```

The `server_default` lets Postgres generate UUIDs for raw SQL inserts
(useful for seeding).

## Timestamps

Always `timestamptz`, not `timestamp`. Always `default=now()` server-side.

```python
from datetime import datetime
from sqlalchemy import DateTime, func

class MyTable(Base):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
```

## Foreign keys

Always specify `ondelete`:

```python
from sqlalchemy import ForeignKey

class Message(Base):
    channel_id: Mapped[UUID] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
    )
```

Choices: `CASCADE`, `SET NULL`, `RESTRICT`. Pick deliberately.

## JSONB columns

For semi-structured data (tags, metadata, weights):

```python
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

class User(Base):
    topic_weights: Mapped[dict[str, float]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
```

Always `JSONB` (not `JSON`) for indexability and binary storage.

## Migration anti-rules

- **NEVER edit a migration after it has been merged.** Even if you find a
  bug. Add a new migration that fixes the bug.
- **NEVER manually edit the database in dev without writing a migration.**
  Your teammate (or future you) won't have those changes.
- **NEVER use `alembic stamp` to skip migrations** unless you know exactly
  what you're doing and why.
- **NEVER include data migrations in the same revision as schema migrations**
  unless the data migration is trivial. Use a separate revision.

## Reviewing the generated migration

After `alembic revision --autogenerate`, open the file and check:

- [ ] The `upgrade()` function does what you intended
- [ ] The `downgrade()` function is the inverse
- [ ] Indexes you wanted are present
- [ ] Special-case items (extensions, custom indexes) added if needed
- [ ] No accidental drops of tables/columns you didn't intend to remove
  (autogenerate sometimes thinks a model is gone if imports break)

## Testing the migration

```bash
# Apply
cd apps/api && uv run alembic upgrade head

# Verify tables
psql -h localhost -U evercurrent -d evercurrent -c "\dt"

# Test downgrade
uv run alembic downgrade -1

# Re-apply
uv run alembic upgrade head
```

A migration that doesn't round-trip cleanly is a bug.

## Common mistakes

- Forgetting `CREATE EXTENSION vector` in the initial migration.
- Manually adding HNSW indexes via SQL outside Alembic (won't replicate
  to other devs).
- Using `timestamp` instead of `timestamptz`.
- Forgetting `ondelete=` on foreign keys.
- Mixing model edits and migration edits across multiple commits — the
  schema state will be inconsistent.
