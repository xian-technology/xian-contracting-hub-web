from __future__ import annotations

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.models import Contract, ContractPackageKind, PublicationStatus
from contracting_hub.services import (
    ContractPackageServiceError,
    ContractPackageServiceErrorCode,
    attach_contract_version_to_package_release,
    create_contract_package,
    create_contract_package_release,
    create_contract_version,
    load_contract_package_release_snapshot,
)


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    ModelRegistry.get_metadata().create_all(engine)
    return engine


def _create_contract(session: Session) -> Contract:
    contract = Contract(
        slug="xian-dex-router",
        contract_name="con_dex",
        display_name="DEX Router",
        short_summary="Router contract for AMM swaps.",
        long_description="Router-style liquidity and swap entrypoints.",
        status=PublicationStatus.PUBLISHED,
        source_repository_url="https://github.com/xian-technology/xian-dex",
    )
    session.add(contract)
    session.commit()
    session.refresh(contract)
    return contract


def _valid_source() -> str:
    return "@export\ndef getAmountsOut(amountIn: int):\n    return amountIn\n"


def _seed_package_release(session: Session) -> tuple[int, str]:
    package = create_contract_package(
        session=session,
        slug="xian-dex",
        display_name="Xian DEX",
        short_summary="Canonical AMM product package.",
        long_description="Contracts, frontend, and deployment manifest for the Xian DEX.",
        kind=ContractPackageKind.PRODUCT,
        status=PublicationStatus.PUBLISHED,
        source_repository_url="https://github.com/xian-technology/xian-dex",
        tags=["dex", "amm", "dex"],
    )
    release = create_contract_package_release(
        session=session,
        package_slug=package.slug,
        semantic_version="0.1.0",
        status=PublicationStatus.PUBLISHED,
        source_commit="5c7b85bef8a558622a0223b3c9b2162566e6fdd6",
        manifest_path="contract-bundle.json",
        manifest_hash_sha256="f" * 64,
        release_notes="Initial DEX package release.",
    )
    return release.id, package.slug


def test_package_service_creates_release_with_contract_artifact() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = _create_contract(session)
        version = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="0.1.0",
            source_code=_valid_source(),
            status=PublicationStatus.PUBLISHED,
        )
        release_id, package_slug = _seed_package_release(session)

        artifact = attach_contract_version_to_package_release(
            session=session,
            release_id=release_id,
            contract_version_id=version.id,
            role="router",
            source_path="src/con_dex.py",
            source_hash_sha256=version.source_hash_sha256,
            deploy_order=20,
            default_chi=200000,
            manifest_metadata={"role": "router"},
        )
        snapshot = load_contract_package_release_snapshot(
            session=session,
            package_slug=package_slug,
        )

        assert artifact.source_hash_sha256 == version.source_hash_sha256
        assert snapshot.found is True
        assert snapshot.package_slug == "xian-dex"
        assert snapshot.semantic_version == "0.1.0"
        assert snapshot.source_commit == "5c7b85bef8a558622a0223b3c9b2162566e6fdd6"
        assert snapshot.manifest_path == "contract-bundle.json"
        assert len(snapshot.artifacts) == 1
        assert snapshot.artifacts[0].contract_name == "con_dex"
        assert snapshot.artifacts[0].role == "router"
        assert snapshot.artifacts[0].source_path == "src/con_dex.py"
        assert snapshot.artifacts[0].default_chi == 200000


def test_package_service_rejects_package_artifact_hash_mismatch() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        contract = _create_contract(session)
        version = create_contract_version(
            session=session,
            contract_slug=contract.slug,
            semantic_version="0.1.0",
            source_code=_valid_source(),
            status=PublicationStatus.PUBLISHED,
        )
        release_id, _package_slug = _seed_package_release(session)

        try:
            attach_contract_version_to_package_release(
                session=session,
                release_id=release_id,
                contract_version_id=version.id,
                source_hash_sha256="0" * 64,
            )
        except ContractPackageServiceError as error:
            assert error.code is ContractPackageServiceErrorCode.HASH_MISMATCH
            assert error.details["expected_hash"] == version.source_hash_sha256
        else:
            raise AssertionError("Expected package artifact hash mismatch to fail")


def test_package_service_rejects_duplicate_package_release() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        _seed_package_release(session)

        try:
            create_contract_package_release(
                session=session,
                package_slug="xian-dex",
                semantic_version="0.1.0",
            )
        except ContractPackageServiceError as error:
            assert error.code is ContractPackageServiceErrorCode.DUPLICATE_RELEASE
        else:
            raise AssertionError("Expected duplicate package release to fail")
