from pathlib import Path

import pytest

from contracting_hub.config import load_settings
from contracting_hub.integrations.storage import (
    IMAGE_UPLOAD_CONTENT_TYPES,
    LocalFileStorage,
    UploadCandidate,
    UploadConstraints,
    UploadValidationError,
    UploadValidationErrorCode,
    avatar_upload_constraints,
    validate_upload,
)
from contracting_hub.services.uploads import (
    build_managed_upload_constraints,
    delete_managed_upload,
    get_upload_storage,
    store_avatar_upload,
)


def test_local_file_storage_saves_uploads_beneath_the_storage_root(tmp_path: Path) -> None:
    storage = LocalFileStorage(root_dir=tmp_path / "uploads")
    stored_upload = storage.save(
        UploadCandidate(
            filename="Profile Photo.PNG",
            content=b"avatar-bytes",
            content_type="image/png",
        ),
        subdir="avatars/profile-images",
        constraints=UploadConstraints(
            max_bytes=1024,
            allowed_extensions=frozenset({".png"}),
            allowed_content_types=frozenset({"image/png"}),
        ),
    )

    assert stored_upload.storage_key.startswith("avatars/profile-images/profile-photo-")
    assert stored_upload.absolute_path.exists()
    assert stored_upload.absolute_path.read_bytes() == b"avatar-bytes"
    assert tmp_path.resolve() in stored_upload.absolute_path.parents


def test_local_file_storage_rejects_parent_path_traversal(tmp_path: Path) -> None:
    storage = LocalFileStorage(root_dir=tmp_path / "uploads")

    with pytest.raises(UploadValidationError) as error:
        storage.save(
            UploadCandidate(
                filename="avatar.png",
                content=b"bytes",
                content_type="image/png",
            ),
            subdir="../avatars",
        )

    assert error.value.code is UploadValidationErrorCode.INVALID_STORAGE_KEY


def test_avatar_upload_constraints_use_avatar_specific_limits(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={"CONTRACTING_HUB_AVATAR_UPLOAD_MAX_BYTES": "2048"},
        env_file=tmp_path / ".env",
    )

    constraints = avatar_upload_constraints(settings)

    assert constraints.max_bytes == 2048
    assert constraints.allowed_content_types == IMAGE_UPLOAD_CONTENT_TYPES
    assert ".png" in constraints.allowed_extensions


def test_validate_upload_rejects_invalid_avatar_content_type() -> None:
    upload = UploadCandidate(
        filename="avatar.png",
        content=b"not-really-an-image",
        content_type="application/octet-stream",
    )

    with pytest.raises(UploadValidationError) as error:
        validate_upload(
            upload,
            UploadConstraints(
                max_bytes=1024,
                allowed_extensions=frozenset({".png"}),
                allowed_content_types=frozenset({"image/png"}),
            ),
        )

    assert error.value.code is UploadValidationErrorCode.UNSUPPORTED_CONTENT_TYPE


def test_store_avatar_upload_uses_avatar_subdirectory_and_can_be_deleted(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={"CONTRACTING_HUB_AVATAR_UPLOAD_DIR": "profile-images"},
        env_file=tmp_path / ".env",
    )
    storage = get_upload_storage(settings)

    stored_upload = store_avatar_upload(
        filename="Author Portrait.jpg",
        content=b"jpeg-bytes",
        content_type="image/jpeg",
        settings=settings,
        storage=storage,
    )

    assert stored_upload.storage_key.startswith("profile-images/author-portrait-")
    assert stored_upload.absolute_path.is_file()

    deleted = delete_managed_upload(stored_upload.storage_key, settings=settings, storage=storage)

    assert deleted is True
    assert not stored_upload.absolute_path.exists()


def test_build_managed_upload_constraints_use_default_size_limit(tmp_path: Path) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={"CONTRACTING_HUB_UPLOAD_MAX_BYTES": "4096"},
        env_file=tmp_path / ".env",
    )

    constraints = build_managed_upload_constraints(settings, allowed_extensions=frozenset({".txt"}))

    assert constraints.max_bytes == 4096
    assert constraints.allowed_extensions == frozenset({".txt"})
