from pathlib import Path

import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session, select

from contracting_hub.config import PROJECT_ROOT, load_settings
from contracting_hub.models import AdminAuditLog, Contract, User
from contracting_hub.services.bootstrap import (
    DEMO_AUDIT_LOG_DEFINITIONS,
    DEMO_CONTRACT_DEFINITIONS,
    DEMO_DEPLOYMENT_DEFINITIONS,
    DEMO_PLAYGROUND_TARGET_DEFINITIONS,
    DEMO_USER_DEFINITIONS,
    seed_local_development_data,
)
from contracting_hub.services.contract_detail import load_public_contract_detail_snapshot
from contracting_hub.services.deployment_history import load_private_deployment_history_snapshot
from contracting_hub.services.developer_profiles import load_public_developer_profile_snapshot
from contracting_hub.services.homepage import load_public_home_page_snapshot
from contracting_hub.services.local_reset import reset_local_development_environment


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    ModelRegistry.get_metadata().create_all(engine)
    return engine


def test_seed_local_development_data_with_demo_data_populates_key_product_surfaces(
    tmp_path: Path,
) -> None:
    settings = load_settings(project_root=tmp_path, environ={}, env_file=tmp_path / ".env")
    engine = _build_engine()

    with Session(engine) as session:
        report = seed_local_development_data(
            settings=settings,
            session=session,
            include_demo_data=True,
        )
        homepage_snapshot = load_public_home_page_snapshot(session=session)
        detail_snapshot = load_public_contract_detail_snapshot(session=session, slug="escrow")
        developer_snapshot = load_public_developer_profile_snapshot(
            session=session,
            username="alice",
        )
        alice = session.exec(select(User).where(User.email == "alice@example.com")).one()
        history_snapshot = load_private_deployment_history_snapshot(
            session=session,
            user_id=alice.id,
        )
        audit_logs = session.exec(select(AdminAuditLog)).all()

    assert report.schema_ready is True
    assert report.demo_report is not None
    assert report.demo_report.schema_ready is True
    assert report.demo_report.users_created == len(DEMO_USER_DEFINITIONS)
    assert report.demo_report.contracts_created == len(DEMO_CONTRACT_DEFINITIONS)
    assert report.demo_report.deployments_created == len(DEMO_DEPLOYMENT_DEFINITIONS)
    assert report.demo_report.playground_targets_created == len(DEMO_PLAYGROUND_TARGET_DEFINITIONS)
    assert report.demo_report.audit_logs_created == len(DEMO_AUDIT_LOG_DEFINITIONS)

    assert homepage_snapshot.featured_contracts
    assert homepage_snapshot.trending_contracts
    assert homepage_snapshot.recently_updated_contracts
    assert homepage_snapshot.recently_deployed_contracts

    assert detail_snapshot.found is True
    assert detail_snapshot.slug == "escrow"
    assert detail_snapshot.selected_version == "2.0.0"
    assert len(detail_snapshot.available_versions) == 2
    assert detail_snapshot.outgoing_related_contracts
    assert detail_snapshot.selected_version_lint.has_report is True

    assert developer_snapshot.found is True
    assert developer_snapshot.username == "alice"
    assert developer_snapshot.authored_contracts
    assert developer_snapshot.total_deployment_count >= 1

    assert len(history_snapshot.saved_targets) == 2
    assert len(history_snapshot.deployments) == 2
    assert len(audit_logs) == len(DEMO_AUDIT_LOG_DEFINITIONS)


def test_seed_local_development_data_with_demo_data_is_repeatable(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path, environ={}, env_file=tmp_path / ".env")
    engine = _build_engine()

    with Session(engine) as session:
        first_report = seed_local_development_data(
            settings=settings,
            session=session,
            include_demo_data=True,
        )
        second_report = seed_local_development_data(
            settings=settings,
            session=session,
            include_demo_data=True,
        )

    assert first_report.demo_report is not None
    assert second_report.demo_report is not None
    assert first_report.demo_report.users_created == len(DEMO_USER_DEFINITIONS)
    assert first_report.demo_report.contracts_created == len(DEMO_CONTRACT_DEFINITIONS)
    assert second_report.categories_created == 0
    assert second_report.demo_report.users_created == 0
    assert second_report.demo_report.profiles_created == 0
    assert second_report.demo_report.contracts_created == 0
    assert second_report.demo_report.versions_created == 0
    assert second_report.demo_report.relations_created == 0
    assert second_report.demo_report.stars_created == 0
    assert second_report.demo_report.ratings_created == 0
    assert second_report.demo_report.playground_targets_created == 0
    assert second_report.demo_report.deployments_created == 0
    assert second_report.demo_report.audit_logs_created == 0


def test_reset_local_development_environment_rebuilds_database_and_uploads(
    tmp_path: Path,
) -> None:
    instance_dir = tmp_path / "instance"
    uploads_dir = tmp_path / "uploads"
    avatar_dir = uploads_dir / "avatars"
    database_path = instance_dir / "contracting_hub_reset.db"

    instance_dir.mkdir(parents=True, exist_ok=True)
    avatar_dir.mkdir(parents=True, exist_ok=True)
    database_path.write_text("stale database", encoding="utf-8")
    database_path.with_name(f"{database_path.name}-wal").write_text("wal", encoding="utf-8")
    (avatar_dir / "stale-avatar.txt").write_text("stale", encoding="utf-8")

    settings = load_settings(
        project_root=PROJECT_ROOT,
        environ={
            "CONTRACTING_HUB_INSTANCE_DIR": str(instance_dir),
            "CONTRACTING_HUB_UPLOADS_DIR": str(uploads_dir),
            "CONTRACTING_HUB_AVATAR_UPLOAD_DIR": str(avatar_dir),
            "CONTRACTING_HUB_DB_PATH": str(database_path),
        },
        env_file=tmp_path / ".env",
    )

    report = reset_local_development_environment(settings=settings)

    assert report.database_removed is True
    assert report.database_sidecars_removed == 1
    assert report.uploads_cleared is True
    assert report.migrations_applied is True
    assert report.seed_report.demo_report is not None
    assert report.seed_report.demo_report.contracts_created == len(DEMO_CONTRACT_DEFINITIONS)
    assert database_path.exists()
    assert avatar_dir.exists()
    assert not (avatar_dir / "stale-avatar.txt").exists()

    engine = sa.create_engine(settings.database_url)
    with Session(engine) as session:
        contract_count = session.exec(select(sa.func.count()).select_from(Contract)).one()
        admin_user = session.exec(
            select(User).where(User.email == "catalog-admin@example.com")
        ).one()
        admin_username = admin_user.profile.username if admin_user.profile is not None else None

    assert contract_count == len(DEMO_CONTRACT_DEFINITIONS)
    assert admin_username == "catalogadmin"
