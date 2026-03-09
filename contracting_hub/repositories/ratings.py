"""Persistence helpers for contract rating workflows."""

from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import Session, select

from contracting_hub.models import Contract, Rating, User


class RatingRepository:
    """Persistence-oriented helpers for contract rating workflows."""

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

    def get_rating(self, *, user_id: int, contract_id: int) -> Rating | None:
        """Load a persisted rating for one user-contract pair."""
        statement = (
            select(Rating).where(Rating.user_id == user_id).where(Rating.contract_id == contract_id)
        )
        return self._session.exec(statement).first()

    def add_rating(self, rating: Rating) -> Rating:
        """Stage a new rating row and assign its primary key."""
        self._session.add(rating)
        self._session.flush()
        return rating

    def get_contract_rating_stats(self, contract_id: int) -> tuple[int, float | None]:
        """Return the current rating count and average score for a contract."""
        statement = (
            select(sa.func.count(Rating.id), sa.func.avg(Rating.score))
            .select_from(Rating)
            .where(Rating.contract_id == contract_id)
        )
        rating_count, average_score = self._session.exec(statement).one()
        return int(rating_count), float(average_score) if average_score is not None else None


__all__ = ["RatingRepository"]
