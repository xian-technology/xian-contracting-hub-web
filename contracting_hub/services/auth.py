"""Authentication helpers for password- and cookie-based account access."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from contracting_hub.models import AuthSession, Profile, User, UserRole, UserStatus, utc_now
from contracting_hub.repositories import AuthRepository

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,32}$")
MIN_PASSWORD_LENGTH = 8
DEFAULT_AUTH_SESSION_TTL = timedelta(days=30)
PASSWORD_HASH_ALGORITHM = "scrypt"
PASSWORD_HASH_N = 2**14
PASSWORD_HASH_R = 8
PASSWORD_HASH_P = 1
PASSWORD_HASH_DKLEN = 64
PASSWORD_HASH_SALT_BYTES = 16
SESSION_TOKEN_BYTES = 32


@dataclass(frozen=True)
class AuthenticatedSession:
    """A newly authenticated session ready to be persisted in a secure cookie."""

    session_token: str
    expires_at: datetime
    user: User


class AuthServiceErrorCode(StrEnum):
    """Stable auth-service failures exposed to callers."""

    ACCOUNT_DISABLED = "account_disabled"
    AUTHENTICATION_REQUIRED = "authentication_required"
    DUPLICATE_EMAIL = "duplicate_email"
    DUPLICATE_USERNAME = "duplicate_username"
    INSUFFICIENT_ROLE = "insufficient_role"
    INVALID_CREDENTIALS = "invalid_credentials"
    INVALID_EMAIL = "invalid_email"
    INVALID_PASSWORD = "invalid_password"
    INVALID_USERNAME = "invalid_username"


class AuthServiceError(ValueError):
    """Structured service error for auth-related workflows."""

    def __init__(
        self,
        code: AuthServiceErrorCode,
        message: str,
        *,
        field: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
        self.details = details or {}

    def as_payload(self) -> dict[str, object]:
        """Serialize the service failure for UI or API responses."""
        return {
            "code": self.code.value,
            "field": self.field,
            "message": str(self),
            "details": self.details,
        }


def hash_password(password: str) -> str:
    """Return a salted password hash using the stdlib scrypt implementation."""
    raw_password = _validate_registration_password(password)
    salt = secrets.token_bytes(PASSWORD_HASH_SALT_BYTES)
    derived_key = _derive_password_hash(raw_password, salt=salt)
    return "$".join(
        [
            PASSWORD_HASH_ALGORITHM,
            str(PASSWORD_HASH_N),
            str(PASSWORD_HASH_R),
            str(PASSWORD_HASH_P),
            str(PASSWORD_HASH_DKLEN),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derived_key).decode("ascii"),
        ]
    )


def verify_password(password: str, stored_password_hash: str) -> bool:
    """Verify a plaintext password against a stored scrypt hash string."""
    if not isinstance(password, str) or not isinstance(stored_password_hash, str):
        return False

    parsed_hash = _parse_password_hash(stored_password_hash)
    if parsed_hash is None:
        return False

    salt, expected_hash = parsed_hash
    actual_hash = _derive_password_hash(password, salt=salt)
    return hmac.compare_digest(actual_hash, expected_hash)


def build_session_token_hash(session_token: str) -> str:
    """Return the persisted SHA-256 digest for an opaque session token."""
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


def register_user(
    *,
    session: Session,
    email: str,
    username: str,
    password: str,
    display_name: str | None = None,
) -> User:
    """Register a new active user account with a one-to-one public profile."""
    normalized_email = normalize_email(email)
    normalized_username = normalize_username(username)
    raw_password = _validate_registration_password(password)
    normalized_display_name = _normalize_optional_text(display_name)
    repository = AuthRepository(session)

    if repository.get_user_by_email(normalized_email) is not None:
        raise AuthServiceError(
            AuthServiceErrorCode.DUPLICATE_EMAIL,
            "An account with this email already exists.",
            field="email",
            details={"email": normalized_email},
        )
    if repository.get_profile_by_username(normalized_username) is not None:
        raise AuthServiceError(
            AuthServiceErrorCode.DUPLICATE_USERNAME,
            "This username is already in use.",
            field="username",
            details={"username": normalized_username},
        )

    user = User(
        email=normalized_email,
        password_hash=hash_password(raw_password),
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    user.profile = Profile(
        username=normalized_username,
        display_name=normalized_display_name,
    )

    try:
        repository.add_user(user)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        _reraise_duplicate_registration_error(
            error,
            email=normalized_email,
            username=normalized_username,
        )
        raise

    return user


def login_user(
    *,
    session: Session,
    email: str,
    password: str,
    session_ttl: timedelta = DEFAULT_AUTH_SESSION_TTL,
    now: datetime | None = None,
) -> AuthenticatedSession:
    """Authenticate a user and persist a new cookie session."""
    normalized_email = normalize_email(email)
    raw_password = _validate_login_password(password)
    validated_ttl = _validate_session_ttl(session_ttl)
    repository = AuthRepository(session)
    user = repository.get_user_by_email(normalized_email)

    if user is None or not verify_password(raw_password, user.password_hash):
        raise AuthServiceError(
            AuthServiceErrorCode.INVALID_CREDENTIALS,
            "The provided email or password is invalid.",
            field="password",
        )
    if user.status is not UserStatus.ACTIVE:
        raise AuthServiceError(
            AuthServiceErrorCode.ACCOUNT_DISABLED,
            "This account is disabled.",
            field="email",
            details={"email": normalized_email},
        )

    issued_at = _coerce_utc_datetime(now or utc_now())
    session_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    auth_session = AuthSession(
        user_id=user.id,
        session_token_hash=build_session_token_hash(session_token),
        expires_at=issued_at + validated_ttl,
    )
    user.last_login_at = issued_at

    repository.add_auth_session(auth_session)
    session.commit()

    return AuthenticatedSession(
        session_token=session_token,
        expires_at=auth_session.expires_at,
        user=user,
    )


def logout_user(
    *,
    session: Session,
    session_token: str | None,
) -> bool:
    """Delete a persisted auth session and make the cookie token unusable."""
    normalized_token = _normalize_session_token(session_token)
    if normalized_token is None:
        return False

    repository = AuthRepository(session)
    auth_session = repository.get_auth_session_by_token_hash(
        build_session_token_hash(normalized_token)
    )
    if auth_session is None:
        return False

    repository.delete_auth_session(auth_session)
    session.commit()
    return True


def resolve_current_user(
    *,
    session: Session,
    session_token: str | None,
    now: datetime | None = None,
) -> User | None:
    """Resolve the current active user from an opaque cookie session token."""
    normalized_token = _normalize_session_token(session_token)
    if normalized_token is None:
        return None

    repository = AuthRepository(session)
    auth_session = repository.get_auth_session_by_token_hash(
        build_session_token_hash(normalized_token)
    )
    if auth_session is None:
        return None

    if _coerce_utc_datetime(auth_session.expires_at) <= _coerce_utc_datetime(now or utc_now()):
        repository.delete_auth_session(auth_session)
        session.commit()
        return None
    if auth_session.user.status is not UserStatus.ACTIVE:
        repository.delete_auth_session(auth_session)
        session.commit()
        return None

    return auth_session.user


def user_has_role(user: User | None, role: UserRole | str) -> bool:
    """Return whether the user is active and has the required role."""
    if user is None or user.status is not UserStatus.ACTIVE:
        return False
    return user.role is _normalize_user_role(role)


def require_user_role(user: User | None, role: UserRole | str) -> User:
    """Ensure the current user is active and holds the required role."""
    required_role = _normalize_user_role(role)
    if user is None:
        raise AuthServiceError(
            AuthServiceErrorCode.AUTHENTICATION_REQUIRED,
            "Authentication is required for this action.",
            field="session",
        )
    if user.status is not UserStatus.ACTIVE:
        raise AuthServiceError(
            AuthServiceErrorCode.ACCOUNT_DISABLED,
            "This account is disabled.",
            field="session",
            details={"user_id": user.id},
        )
    if user.role is required_role:
        return user

    raise AuthServiceError(
        AuthServiceErrorCode.INSUFFICIENT_ROLE,
        "You do not have permission to perform this action.",
        field="role",
        details={
            "required_role": required_role.value,
            "actual_role": user.role.value,
        },
    )


def normalize_email(email: str) -> str:
    """Normalize and validate a user email address."""
    if not isinstance(email, str):
        raise AuthServiceError(
            AuthServiceErrorCode.INVALID_EMAIL,
            "Email must be a string.",
            field="email",
        )

    normalized_email = email.strip().lower()
    if not normalized_email or not EMAIL_PATTERN.fullmatch(normalized_email):
        raise AuthServiceError(
            AuthServiceErrorCode.INVALID_EMAIL,
            "Enter a valid email address.",
            field="email",
        )
    return normalized_email


def normalize_username(username: str) -> str:
    """Normalize and validate a public developer username."""
    if not isinstance(username, str):
        raise AuthServiceError(
            AuthServiceErrorCode.INVALID_USERNAME,
            "Username must be a string.",
            field="username",
        )

    normalized_username = username.strip().lower()
    if USERNAME_PATTERN.fullmatch(normalized_username):
        return normalized_username

    raise AuthServiceError(
        AuthServiceErrorCode.INVALID_USERNAME,
        "Username must be 3-32 characters using lowercase letters, numbers, or underscores.",
        field="username",
    )


def _derive_password_hash(password: str, *, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_HASH_N,
        r=PASSWORD_HASH_R,
        p=PASSWORD_HASH_P,
        dklen=PASSWORD_HASH_DKLEN,
    )


def _parse_password_hash(stored_password_hash: str) -> tuple[bytes, bytes] | None:
    parts = stored_password_hash.split("$")
    if len(parts) != 7 or parts[0] != PASSWORD_HASH_ALGORITHM:
        return None

    try:
        n_value = int(parts[1])
        r_value = int(parts[2])
        p_value = int(parts[3])
        dklen_value = int(parts[4])
        salt = base64.b64decode(parts[5], validate=True)
        expected_hash = base64.b64decode(parts[6], validate=True)
    except (ValueError, TypeError, binascii.Error):
        return None

    expected_values = (
        n_value == PASSWORD_HASH_N,
        r_value == PASSWORD_HASH_R,
        p_value == PASSWORD_HASH_P,
        dklen_value == PASSWORD_HASH_DKLEN,
        len(expected_hash) == PASSWORD_HASH_DKLEN,
    )
    if all(expected_values):
        return salt, expected_hash
    return None


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized_value = value.strip()
    return normalized_value or None


def _validate_registration_password(password: str) -> str:
    if not isinstance(password, str):
        raise AuthServiceError(
            AuthServiceErrorCode.INVALID_PASSWORD,
            "Password must be a string.",
            field="password",
        )
    if len(password) < MIN_PASSWORD_LENGTH or not password.strip():
        raise AuthServiceError(
            AuthServiceErrorCode.INVALID_PASSWORD,
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.",
            field="password",
        )
    return password


def _validate_login_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise AuthServiceError(
            AuthServiceErrorCode.INVALID_PASSWORD,
            "Password is required.",
            field="password",
        )
    return password


def _validate_session_ttl(session_ttl: timedelta) -> timedelta:
    if session_ttl <= timedelta(0):
        raise ValueError("session_ttl must be positive")
    return session_ttl


def _normalize_session_token(session_token: str | None) -> str | None:
    if session_token is None:
        return None
    normalized_token = session_token.strip()
    return normalized_token or None


def _coerce_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_user_role(role: UserRole | str) -> UserRole:
    if isinstance(role, UserRole):
        return role
    return UserRole(role)


def _reraise_duplicate_registration_error(
    error: IntegrityError,
    *,
    email: str,
    username: str,
) -> None:
    message = str(error.orig).lower()
    if "users.email" in message:
        raise AuthServiceError(
            AuthServiceErrorCode.DUPLICATE_EMAIL,
            "An account with this email already exists.",
            field="email",
            details={"email": email},
        ) from error
    if "profiles.username" in message:
        raise AuthServiceError(
            AuthServiceErrorCode.DUPLICATE_USERNAME,
            "This username is already in use.",
            field="username",
            details={"username": username},
        ) from error


__all__ = [
    "DEFAULT_AUTH_SESSION_TTL",
    "EMAIL_PATTERN",
    "MIN_PASSWORD_LENGTH",
    "PASSWORD_HASH_ALGORITHM",
    "SESSION_TOKEN_BYTES",
    "USERNAME_PATTERN",
    "AuthenticatedSession",
    "AuthServiceError",
    "AuthServiceErrorCode",
    "build_session_token_hash",
    "hash_password",
    "login_user",
    "logout_user",
    "normalize_email",
    "normalize_username",
    "register_user",
    "require_user_role",
    "resolve_current_user",
    "user_has_role",
    "verify_password",
]
