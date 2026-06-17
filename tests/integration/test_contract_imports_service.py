from __future__ import annotations

import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.services import (
    ContractImportError,
    ContractImportErrorCode,
    build_source_hash,
    import_contract_bundle_manifest,
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


def _write_manifest_fixture(root: Path, *, bad_hash: bool = False) -> Path:
    pair_source_path = "src/con_pairs.py"
    router_source_path = "src/con_dex.py"
    pair_source = "\n".join(
        [
            "@export",
            "def pair_for(token_a: str, token_b: str):",
            "    return token_a + token_b",
            "",
        ]
    )
    router_source = "@export\ndef get_amounts_out(amount_in: int):\n    return amount_in\n"
    _write_source(root, pair_source_path, pair_source)
    _write_source(root, router_source_path, router_source)

    pair_hash = build_source_hash(pair_source)
    router_hash = build_source_hash(router_source)
    if bad_hash:
        router_hash = "0" * 64

    manifest = {
        "schema": "xian.contract_bundle.v1",
        "schema_version": 1,
        "name": "xian-dex",
        "display_name": "Xian DEX",
        "version": "0.1.0",
        "description": "Canonical Xian AMM contracts owned by xian-dex.",
        "source": {
            "repo": "https://github.com/xian-technology/xian-dex",
            "commit": "5c7b85bef8a558622a0223b3c9b2162566e6fdd6",
        },
        "contracts": [
            {
                "name": "con_pairs",
                "role": "pairs",
                "path": pair_source_path,
                "sha256": pair_hash,
                "deploy_order": 10,
                "default_chi": 300000,
            },
            {
                "name": "con_dex",
                "role": "router",
                "path": router_source_path,
                "sha256": router_hash,
                "deploy_order": 20,
                "default_chi": 200000,
                "deploy_default": False,
                "deployment_note": "Router is optional in this fixture.",
            },
        ],
        "recipes": [
            {
                "name": "default",
                "contracts": ["con_pairs", "con_dex"],
            }
        ],
    }

    manifest_path = root / "contract-bundle.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def _write_source(root: Path, relative_path: str, source_code: str) -> None:
    source_path = root / relative_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(source_code, encoding="utf-8")


def test_import_contract_bundle_manifest_creates_package_release_artifacts(
    tmp_path: Path,
) -> None:
    engine = _build_engine()
    manifest_path = _write_manifest_fixture(tmp_path)

    with Session(engine) as session:
        report = import_contract_bundle_manifest(
            session=session,
            manifest_path=manifest_path,
        )
        snapshot = load_contract_package_release_snapshot(
            session=session,
            package_slug="xian-dex",
            semantic_version="0.1.0",
        )

    assert report.package_created is True
    assert report.release_created is True
    assert report.contracts_created == 2
    assert report.versions_created == 2
    assert report.artifacts_created == 2
    assert report.contracts_existing == 0
    assert report.warnings == ()

    assert snapshot.found is True
    assert snapshot.package_slug == "xian-dex"
    assert snapshot.package_display_name == "Xian DEX"
    assert snapshot.semantic_version == "0.1.0"
    assert snapshot.source_commit == "5c7b85bef8a558622a0223b3c9b2162566e6fdd6"
    assert snapshot.manifest_path == "contract-bundle.json"
    assert [artifact.role for artifact in snapshot.artifacts] == ["pairs", "router"]
    assert [artifact.contract_name for artifact in snapshot.artifacts] == [
        "con_pairs",
        "con_dex",
    ]
    assert snapshot.artifacts[0].deploy_order == 10
    assert snapshot.artifacts[0].default_chi == 300000
    assert snapshot.artifacts[1].source_path == "src/con_dex.py"
    assert snapshot.artifacts[1].deploy_default is False
    assert snapshot.artifacts[1].manifest_metadata["deployment_note"] == (
        "Router is optional in this fixture."
    )


def test_import_contract_bundle_manifest_is_idempotent(tmp_path: Path) -> None:
    engine = _build_engine()
    manifest_path = _write_manifest_fixture(tmp_path)

    with Session(engine) as session:
        first_report = import_contract_bundle_manifest(
            session=session,
            manifest_path=manifest_path,
        )
        second_report = import_contract_bundle_manifest(
            session=session,
            manifest_path=manifest_path,
        )

    assert first_report.package_created is True
    assert first_report.release_created is True
    assert second_report.package_created is False
    assert second_report.release_created is False
    assert second_report.contracts_created == 0
    assert second_report.contracts_existing == 2
    assert second_report.versions_created == 0
    assert second_report.versions_existing == 2
    assert second_report.artifacts_created == 0
    assert second_report.artifacts_existing == 2


def test_import_contract_bundle_manifest_rejects_source_hash_mismatch(
    tmp_path: Path,
) -> None:
    engine = _build_engine()
    manifest_path = _write_manifest_fixture(tmp_path, bad_hash=True)

    with Session(engine) as session:
        with pytest.raises(ContractImportError) as error:
            import_contract_bundle_manifest(
                session=session,
                manifest_path=manifest_path,
            )

    assert error.value.code is ContractImportErrorCode.SOURCE_HASH_MISMATCH
    assert error.value.field == "contracts[1].sha256"
    assert error.value.details["contract_name"] == "con_dex"
