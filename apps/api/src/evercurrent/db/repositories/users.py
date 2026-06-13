from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from evercurrent.db.models import User as UserModel
from evercurrent.domain.users import Role, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        row = await self._s.get(UserModel, user_id)
        return User.model_validate(row) if row else None

    async def get_by_username(self, project_id: uuid.UUID, username: str) -> User | None:
        result = await self._s.execute(
            select(UserModel).where(
                UserModel.project_id == project_id,
                UserModel.username == username,
            ),
        )
        row = result.scalar_one_or_none()
        return User.model_validate(row) if row else None

    async def list_for_project(self, project_id: uuid.UUID) -> list[User]:
        result = await self._s.execute(
            select(UserModel)
            .where(UserModel.project_id == project_id)
            .order_by(UserModel.display_name),
        )
        return [User.model_validate(r) for r in result.scalars()]

    async def upsert(
        self,
        *,
        project_id: uuid.UUID,
        username: str,
        display_name: str,
        role: Role,
        owned_subsystems: list[str] | None = None,
        owned_parts: list[str] | None = None,
        topic_weights: dict[str, float] | None = None,
    ) -> User:
        stmt = (
            pg_insert(UserModel)
            .values(
                project_id=project_id,
                username=username,
                display_name=display_name,
                role=role.value,
                owned_subsystems=owned_subsystems or [],
                owned_parts=owned_parts or [],
                topic_weights=topic_weights or {},
            )
            .on_conflict_do_update(
                index_elements=[UserModel.project_id, UserModel.username],
                set_={
                    "display_name": display_name,
                    "role": role.value,
                    "owned_subsystems": owned_subsystems or [],
                    "owned_parts": owned_parts or [],
                },
            )
            .returning(UserModel)
        )
        result = await self._s.execute(stmt)
        row = result.scalar_one()
        return User.model_validate(row)

    async def bump_topic_weight(
        self,
        user_id: uuid.UUID,
        topic: str,
        delta: float,
    ) -> User | None:
        row = await self._s.get(UserModel, user_id)
        if row is None:
            return None
        weights = dict(row.topic_weights or {})
        weights[topic] = float(weights.get(topic, 0.0)) + delta
        row.topic_weights = weights
        await self._s.flush()
        return User.model_validate(row)
