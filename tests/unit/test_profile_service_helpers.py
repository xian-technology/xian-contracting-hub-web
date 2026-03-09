import pytest

from contracting_hub.services.profiles import (
    ProfileServiceError,
    ProfileServiceErrorCode,
    normalize_profile_bio,
    normalize_profile_display_name,
    normalize_profile_url,
)


def test_profile_text_normalizers_trim_blank_values() -> None:
    assert normalize_profile_display_name("  Alice Validator  ") == "Alice Validator"
    assert normalize_profile_display_name("   ") is None
    assert normalize_profile_bio("  Building reusable Xian modules.  ") == (
        "Building reusable Xian modules."
    )
    assert normalize_profile_bio("") is None


def test_profile_text_normalizers_reject_invalid_types_and_lengths() -> None:
    with pytest.raises(ProfileServiceError) as display_name_error:
        normalize_profile_display_name(123)  # type: ignore[arg-type]

    with pytest.raises(ProfileServiceError) as bio_error:
        normalize_profile_bio("x" * 1001)

    assert display_name_error.value.code is ProfileServiceErrorCode.INVALID_DISPLAY_NAME
    assert bio_error.value.code is ProfileServiceErrorCode.INVALID_BIO


def test_normalize_profile_url_accepts_http_https_and_rejects_invalid_values() -> None:
    assert normalize_profile_url(" https://example.com/alice ", field="website_url") == (
        "https://example.com/alice"
    )
    assert normalize_profile_url("", field="github_url") is None

    with pytest.raises(ProfileServiceError) as invalid_scheme_error:
        normalize_profile_url("ftp://example.com/alice", field="website_url")

    with pytest.raises(ProfileServiceError) as missing_host_error:
        normalize_profile_url("https:///missing-host", field="xian_profile_url")

    assert invalid_scheme_error.value.code is ProfileServiceErrorCode.INVALID_URL
    assert invalid_scheme_error.value.field == "website_url"
    assert missing_host_error.value.code is ProfileServiceErrorCode.INVALID_URL
    assert missing_host_error.value.field == "xian_profile_url"
