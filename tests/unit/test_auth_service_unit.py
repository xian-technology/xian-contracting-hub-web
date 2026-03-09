from contracting_hub.models import User, UserRole, UserStatus
from contracting_hub.services.auth import (
    AuthServiceError,
    AuthServiceErrorCode,
    hash_password,
    normalize_email,
    normalize_username,
    require_user_role,
    user_has_role,
    verify_password,
)


def test_hash_password_uses_salted_hashes_and_verifies_plaintext() -> None:
    first_hash = hash_password("correct horse battery staple")
    second_hash = hash_password("correct horse battery staple")

    assert first_hash != second_hash
    assert verify_password("correct horse battery staple", first_hash) is True
    assert verify_password("wrong password", first_hash) is False


def test_verify_password_returns_false_for_unrecognized_hash_format() -> None:
    assert verify_password("secret", "plain-text-value") is False


def test_email_and_username_normalization_trim_and_lowercase() -> None:
    assert normalize_email("  Alice@Example.COM ") == "alice@example.com"
    assert normalize_username("  Alice_Validator ") == "alice_validator"


def test_require_user_role_checks_authentication_status_and_role() -> None:
    active_admin = User(
        email="admin@example.com",
        password_hash="hashed",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    disabled_admin = User(
        email="disabled@example.com",
        password_hash="hashed",
        role=UserRole.ADMIN,
        status=UserStatus.DISABLED,
    )

    assert user_has_role(active_admin, UserRole.ADMIN) is True
    assert require_user_role(active_admin, UserRole.ADMIN) is active_admin
    assert user_has_role(disabled_admin, UserRole.ADMIN) is False

    try:
        require_user_role(None, UserRole.USER)
    except AuthServiceError as error:
        assert error.code is AuthServiceErrorCode.AUTHENTICATION_REQUIRED
    else:
        raise AssertionError("Expected missing user to require authentication")

    try:
        require_user_role(active_admin, UserRole.USER)
    except AuthServiceError as error:
        assert error.code is AuthServiceErrorCode.INSUFFICIENT_ROLE
    else:
        raise AssertionError("Expected role mismatch to fail")

    try:
        require_user_role(disabled_admin, UserRole.ADMIN)
    except AuthServiceError as error:
        assert error.code is AuthServiceErrorCode.ACCOUNT_DISABLED
    else:
        raise AssertionError("Expected disabled user to fail role checks")
