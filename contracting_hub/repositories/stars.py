"""Persistence helpers for star and favorite workflows."""

from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import Session, select

from contracting_hub.models import Contract, Star, User


class StarRepository:
    """Persistence-oriented helpers for star toggle workflows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_by_id(self, user_id: int) -> User | None:
        """Load a user row by primary key."""
        statement = select(User).where(User.id == user_id)
        return self._session.exec(statement).first()

    def get_contract_by_slug(self, slug: str) -> Contract | None:
        """Load a contract row by its stable slug."""
        statement = select(Contract).where(Contract.slug == slug)
        return self._session.exec(statement).first()

    def get_star(self, *, user_id: int, contract_id: int) -> Star | None:
        """Load a persisted favorite record for one user-contract pair."""
        statement = (
            select(Star).where(Star.user_id == user_id).where(Star.contract_id == contract_id)
        )
        return self._session.exec(statement).first()

    def count_contract_stars(self, contract_id: int) -> int:
        """Return the current favorite total for a contract."""
        statement = select(sa.func.count()).select_from(Star).where(Star.contract_id == contract_id)
        return int(self._session.exec(statement).one())

    def add_star(self, star: Star) -> Star:
        """Stage a new favorite row and assign its primary key."""
        self._session.add(star)
        self._session.flush()
        return star

    def delete_star(self, star: Star) -> None:
        """Stage removal of an existing favorite row."""
        self._session.delete(star)


__all__ = ["StarRepository"]
