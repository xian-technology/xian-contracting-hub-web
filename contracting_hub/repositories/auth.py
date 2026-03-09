"""Repository helpers for authentication and session persistence."""

from __future__ import annotations

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from contracting_hub.models import AuthSession, Profile, User


class AuthRepository:
    """Persistence helpers used by auth services."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_by_id(self, user_id: int) -> User | None:
        """Load a user by primary key, including the public profile."""
        statement = select(User).options(selectinload(User.profile)).where(User.id == user_id)
        return self._session.exec(statement).first()

    def get_user_by_email(self, email: str) -> User | None:
        """Load a user by normalized email, including the public profile."""
        statement = select(User).options(selectinload(User.profile)).where(User.email == email)
        return self._session.exec(statement).first()

    def get_profile_by_username(self, username: str) -> Profile | None:
        """Load a profile by normalized username."""
        statement = select(Profile).where(Profile.username == username)
        return self._session.exec(statement).first()

    def add_user(self, user: User) -> None:
        """Persist a new user row and assign a primary key."""
        self._session.add(user)
        self._session.flush()

    def get_auth_session_by_token_hash(self, token_hash: str) -> AuthSession | None:
        """Load an auth session and the owning user for a hashed cookie token."""
        statement = (
            select(AuthSession)
            .options(selectinload(AuthSession.user).selectinload(User.profile))
            .where(AuthSession.session_token_hash == token_hash)
        )
        return self._session.exec(statement).first()

    def add_auth_session(self, auth_session: AuthSession) -> None:
        """Persist an auth session row and assign a primary key."""
        self._session.add(auth_session)
        self._session.flush()

    def delete_auth_session(self, auth_session: AuthSession) -> None:
        """Remove an auth session record."""
        self._session.delete(auth_session)
