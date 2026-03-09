from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.models import (
    Contract,
    ContractVersion,
    DeploymentHistory,
    DeploymentStatus,
    DeploymentTransport,
    PlaygroundTarget,
    Profile,
    PublicationStatus,
    User,
)
from contracting_hub.services.deployment_history import load_private_deployment_history_snapshot


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")
    ModelRegistry.get_metadata().create_all(engine)
    return engine


def test_load_private_deployment_history_snapshot_lists_recent_attempts_and_saved_targets() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = User(email="alice@example.com", password_hash="hashed-password")
        user.profile = Profile(username="alice", display_name="Alice")

        escrow = Contract(
            slug="escrow",
            contract_name="con_escrow",
            display_name="Escrow",
            short_summary="Escrow primitives.",
            long_description="Escrow description.",
            author=user,
            status=PublicationStatus.PUBLISHED,
        )
        escrow_version = ContractVersion(
            contract=escrow,
            semantic_version="1.1.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'escrow'\n",
            source_hash_sha256="a" * 64,
        )
        escrow.latest_published_version = escrow_version

        vault = Contract(
            slug="vault",
            contract_name="con_vault",
            display_name="Vault",
            short_summary="Vault primitives.",
            long_description="Vault description.",
            author=user,
            status=PublicationStatus.PUBLISHED,
        )
        vault_version = ContractVersion(
            contract=vault,
            semantic_version="0.9.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'vault'\n",
            source_hash_sha256="b" * 64,
        )
        vault.latest_published_version = vault_version

        target = PlaygroundTarget(
            user=user,
            label="Sandbox primary",
            playground_id="sandbox-main",
            is_default=True,
            last_used_at=datetime(2026, 3, 9, 12, 5, tzinfo=timezone.utc),
        )
        session.add(target)
        session.flush()

        redirect_deployment = DeploymentHistory(
            user_id=user.id,
            contract_version_id=escrow_version.id,
            playground_target_id=target.id,
            playground_id="sandbox-main",
            status=DeploymentStatus.REDIRECT_REQUIRED,
            transport=DeploymentTransport.DEEP_LINK,
            redirect_url="https://playground.local/deploy?payload=encoded",
            external_request_id="req-redirect",
            request_payload={"playground_id": "sandbox-main"},
            response_payload={"status": "redirect_required"},
            initiated_at=datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 3, 9, 12, 1, tzinfo=timezone.utc),
        )
        failed_deployment = DeploymentHistory(
            user_id=user.id,
            contract_version_id=vault_version.id,
            playground_target_id=None,
            playground_id="adhoc-target",
            status=DeploymentStatus.FAILED,
            transport=DeploymentTransport.HTTP,
            request_payload={"playground_id": "adhoc-target"},
            error_payload={"message": "Playground rejected the deployment payload."},
            initiated_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 3, 8, 10, 2, tzinfo=timezone.utc),
        )
        session.add(redirect_deployment)
        session.add(failed_deployment)
        session.commit()

        snapshot = load_private_deployment_history_snapshot(session=session, user_id=user.id)

    assert len(snapshot.saved_targets) == 1
    assert snapshot.saved_targets[0].label == "Sandbox primary"
    assert snapshot.saved_targets[0].playground_id == "sandbox-main"

    assert [entry.contract_slug for entry in snapshot.deployments] == ["escrow", "vault"]
    assert snapshot.deployments[0].status is DeploymentStatus.REDIRECT_REQUIRED
    assert snapshot.deployments[0].playground_target_label == "Sandbox primary"
    assert snapshot.deployments[1].error_message == "Playground rejected the deployment payload."
