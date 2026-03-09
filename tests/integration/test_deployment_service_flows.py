from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.config import load_settings
from contracting_hub.integrations import (
    PlaygroundAdapterCapabilities,
    PlaygroundAdapterError,
    PlaygroundAdapterErrorCode,
    PlaygroundDeploymentResult,
    PlaygroundDispatchStatus,
    PlaygroundTransport,
)
from contracting_hub.models import (
    Contract,
    ContractNetwork,
    ContractVersion,
    DeploymentHistory,
    DeploymentStatus,
    PlaygroundTarget,
    Profile,
    PublicationStatus,
    User,
)
from contracting_hub.services.deployments import (
    ContractDeploymentServiceError,
    ContractDeploymentServiceErrorCode,
    deploy_contract_version,
)


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")
    ModelRegistry.get_metadata().create_all(engine)
    return engine


class RedirectAdapter:
    name = "redirect-test"
    capabilities = PlaygroundAdapterCapabilities(
        transport=PlaygroundTransport.DEEP_LINK,
        supports_redirects=True,
        supports_request_tracking=False,
    )

    def submit_deployment(self, request):
        return PlaygroundDeploymentResult(
            status=PlaygroundDispatchStatus.REDIRECT_REQUIRED,
            transport=PlaygroundTransport.DEEP_LINK,
            message="Open the playground redirect.",
            request_payload=request.as_payload(),
            redirect_url="https://playground.local/deploy?payload=encoded",
        )


class RejectingAdapter:
    name = "rejecting-test"
    capabilities = PlaygroundAdapterCapabilities(
        transport=PlaygroundTransport.HTTP,
        supports_redirects=False,
        supports_request_tracking=True,
    )

    def submit_deployment(self, request):
        raise PlaygroundAdapterError(
            PlaygroundAdapterErrorCode.PAYLOAD_REJECTED,
            "Playground rejected the deployment payload.",
            retryable=False,
            upstream_status=422,
            details={"field": "contract.source_code"},
        )


def _seed_contract_graph(session: Session) -> tuple[int, int, int]:
    user = User(email="alice@example.com", password_hash="hashed-password")
    user.profile = Profile(username="alice", display_name="Alice")
    contract = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Escrow primitives.",
        long_description="Long-form escrow description.",
        author=user,
        status=PublicationStatus.PUBLISHED,
        network=ContractNetwork.SANDBOX,
    )
    version = ContractVersion(
        contract=contract,
        semantic_version="1.2.0",
        status=PublicationStatus.PUBLISHED,
        source_code="def seed():\n    return 'ok'\n",
        source_hash_sha256="a" * 64,
        changelog="Add timeout support",
    )
    contract.latest_published_version = version
    target = PlaygroundTarget(
        user=user,
        label="Sandbox",
        playground_id="target-123",
        is_default=True,
    )

    session.add(target)
    session.commit()

    return user.id, version.id, target.id


def test_deploy_contract_version_records_redirect_history_for_saved_targets() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user_id, version_id, target_id = _seed_contract_graph(session)

        result = deploy_contract_version(
            session=session,
            user_id=user_id,
            contract_slug="escrow",
            semantic_version="1.2.0",
            playground_target_id=target_id,
            adapter=RedirectAdapter(),
            client_context={"request_origin": "contract_detail"},
        )

        deployment = session.exec(
            select(DeploymentHistory).where(DeploymentHistory.id == result.deployment_id)
        ).one()
        target = session.exec(
            select(PlaygroundTarget).where(PlaygroundTarget.id == target_id)
        ).one()

    assert result.status is DeploymentStatus.REDIRECT_REQUIRED
    assert result.playground_id == "target-123"
    assert result.playground_target_id == target_id
    assert result.redirect_url == "https://playground.local/deploy?payload=encoded"
    assert result.error_payload is None
    assert deployment.contract_version_id == version_id
    assert deployment.response_payload == {
        "status": "redirect_required",
        "transport": "deep_link",
        "message": "Open the playground redirect.",
        "redirect_url": "https://playground.local/deploy?payload=encoded",
    }
    assert deployment.request_payload["contract"]["metadata"] == {
        "author_username": "alice",
        "network": "sandbox",
    }
    assert target.last_used_at is not None


def test_deploy_contract_version_records_failed_history_for_adapter_errors() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user_id, _, target_id = _seed_contract_graph(session)

        result = deploy_contract_version(
            session=session,
            user_id=user_id,
            contract_slug="escrow",
            semantic_version="1.2.0",
            playground_target_id=target_id,
            adapter=RejectingAdapter(),
        )

        deployment = session.exec(
            select(DeploymentHistory).where(DeploymentHistory.id == result.deployment_id)
        ).one()

    assert result.status is DeploymentStatus.FAILED
    assert result.transport is not None
    assert result.response_payload is None
    assert result.error_payload == {
        "code": "payload_rejected",
        "message": "Playground rejected the deployment payload.",
        "retryable": False,
        "upstream_status": 422,
        "details": {"field": "contract.source_code"},
    }
    assert deployment.status is DeploymentStatus.FAILED
    assert deployment.error_payload == result.error_payload


def test_deploy_contract_version_uses_ad_hoc_playground_ids_and_default_adapter(
    tmp_path,
) -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user_id, _, _ = _seed_contract_graph(session)
        settings = load_settings(
            project_root=tmp_path,
            environ={
                "CONTRACTING_HUB_PLAYGROUND_DEEP_LINK_BASE_URL": "https://playground.local/deploy"
            },
            env_file=tmp_path / ".env",
        )

        result = deploy_contract_version(
            session=session,
            user_id=user_id,
            contract_slug="escrow",
            semantic_version="1.2.0",
            playground_id=" adhoc-target ",
            settings=settings,
            callback_url="https://hub.local/deployments/callback",
        )

    query = parse_qs(urlsplit(result.redirect_url or "").query)

    assert result.playground_id == "adhoc-target"
    assert result.status is DeploymentStatus.REDIRECT_REQUIRED
    assert query["payload"]
    assert result.request_payload["deployment"]["callback_url"] == (
        "https://hub.local/deployments/callback"
    )


def test_deploy_contract_version_allows_blank_ad_hoc_id_with_saved_target() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user_id, version_id, target_id = _seed_contract_graph(session)

        result = deploy_contract_version(
            session=session,
            user_id=user_id,
            contract_slug="escrow",
            semantic_version="1.2.0",
            playground_target_id=target_id,
            playground_id="   ",
            adapter=RedirectAdapter(),
        )

        deployment = session.exec(
            select(DeploymentHistory).where(DeploymentHistory.id == result.deployment_id)
        ).one()

    assert result.status is DeploymentStatus.REDIRECT_REQUIRED
    assert result.playground_id == "target-123"
    assert result.playground_target_id == target_id
    assert deployment.contract_version_id == version_id
    assert deployment.playground_id == "target-123"
    assert deployment.playground_target_id == target_id
    assert deployment.request_payload["playground_id"] == "target-123"


def test_deploy_contract_version_rejects_draft_versions_without_recording_history() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = User(email="bob@example.com", password_hash="hashed-password")
        contract = Contract(
            slug="draft-contract",
            contract_name="con_draft_contract",
            display_name="Draft Contract",
            short_summary="Draft summary.",
            long_description="Draft long description.",
            author=user,
            status=PublicationStatus.DRAFT,
        )
        version = ContractVersion(
            contract=contract,
            semantic_version="0.1.0",
            status=PublicationStatus.DRAFT,
            source_code="def seed():\n    return 'draft'\n",
            source_hash_sha256="b" * 64,
        )

        session.add(version)
        session.commit()

        with pytest.raises(ContractDeploymentServiceError) as error:
            deploy_contract_version(
                session=session,
                user_id=user.id,
                contract_slug="draft-contract",
                semantic_version="0.1.0",
                playground_id="target-123",
                adapter=RedirectAdapter(),
            )
        deployment_count = session.exec(
            select(sa.func.count()).select_from(DeploymentHistory)
        ).one()

    assert error.value.code is ContractDeploymentServiceErrorCode.CONTRACT_VERSION_NOT_DEPLOYABLE
    assert deployment_count == 0
