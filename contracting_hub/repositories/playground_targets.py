"""Persistence helpers for saved playground target workflows."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.models import PlaygroundTarget, User


class PlaygroundTargetRepository:
    """Persistence-oriented helpers for saved playground target workflows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_by_id(self, user_id: int) -> User | None:
        """Load a user row and any saved playground targets."""
        statement = (
            select(User).options(selectinload(User.playground_targets)).where(User.id == user_id)
        )
        return self._session.exec(statement).first()

    def list_targets_for_user(self, *, user_id: int) -> list[PlaygroundTarget]:
        """Return saved playground targets ordered for UI selection."""
        statement = (
            select(PlaygroundTarget)
            .where(PlaygroundTarget.user_id == user_id)
            .order_by(
                PlaygroundTarget.is_default.desc(),
                sa.case((PlaygroundTarget.last_used_at.is_(None), 1), else_=0),
                PlaygroundTarget.last_used_at.desc(),
                PlaygroundTarget.created_at.desc(),
                PlaygroundTarget.id.desc(),
            )
        )
        return list(self._session.exec(statement).all())

    def get_target_by_id(self, *, user_id: int, target_id: int) -> PlaygroundTarget | None:
        """Load one saved target for the owning user."""
        statement = (
            select(PlaygroundTarget)
            .where(PlaygroundTarget.user_id == user_id)
            .where(PlaygroundTarget.id == target_id)
        )
        return self._session.exec(statement).first()

    def get_target_by_playground_id(
        self,
        *,
        user_id: int,
        playground_id: str,
    ) -> PlaygroundTarget | None:
        """Load one saved target by normalized playground identifier."""
        statement = (
            select(PlaygroundTarget)
            .where(PlaygroundTarget.user_id == user_id)
            .where(PlaygroundTarget.playground_id == playground_id)
        )
        return self._session.exec(statement).first()

    def add_target(self, target: PlaygroundTarget) -> PlaygroundTarget:
        """Stage a new saved target row and assign a primary key."""
        self._session.add(target)
        self._session.flush()
        return target

    def delete_target(self, target: PlaygroundTarget) -> None:
        """Stage removal of an existing saved target row."""
        self._session.delete(target)


__all__ = ["PlaygroundTargetRepository"]
