import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from contracting_hub.models import (
    AdminAuditLog,
    Category,
    Contract,
    ContractCategoryLink,
    ContractNetwork,
    ContractRelation,
    ContractRelationType,
    ContractVersion,
    DeploymentHistory,
    DeploymentStatus,
    DeploymentTransport,
    PlaygroundTarget,
    Profile,
    PublicationStatus,
    Rating,
    Star,
    User,
    UserRole,
)


def _build_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from reflex.model import ModelRegistry

    ModelRegistry.get_metadata().create_all(engine)
    return engine


def test_domain_models_support_catalog_relationships() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        author = User(
            email="alice@example.com",
            password_hash="hashed-password",
            role=UserRole.ADMIN,
        )
        author.profile = Profile(
            username="alice",
            display_name="Alice",
            github_url="https://github.com/alice",
        )
        category = Category(slug="finance", name="Finance", sort_order=10)
        contract = Contract(
            slug="escrow",
            contract_name="con_escrow",
            display_name="Escrow",
            short_summary="Escrow primitives for sandbox use.",
            long_description="Long-form description for the escrow contract.",
            author=author,
            status=PublicationStatus.PUBLISHED,
            featured=True,
            network=ContractNetwork.SANDBOX,
            tags=["finance", "escrow"],
        )
        version = ContractVersion(
            contract=contract,
            semantic_version="1.0.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'ok'\n",
            source_hash_sha256="a" * 64,
            changelog="Initial release",
        )
        contract.latest_published_version = version
        category_link = ContractCategoryLink(
            contract=contract,
            category=category,
            is_primary=True,
        )

        companion = Contract(
            slug="token",
            contract_name="con_token",
            display_name="Token",
            short_summary="Companion token module.",
            long_description="Long-form description for the companion token contract.",
            status=PublicationStatus.PUBLISHED,
            author_label="Core team",
            tags=["token"],
        )
        companion_version = ContractVersion(
            contract=companion,
            semantic_version="0.9.0",
            status=PublicationStatus.PUBLISHED,
            source_code="def seed():\n    return 'token'\n",
            source_hash_sha256="b" * 64,
        )
        companion.latest_published_version = companion_version
        relation = ContractRelation(
            source_contract=contract,
            target_contract=companion,
            relation_type=ContractRelationType.DEPENDS_ON,
        )
        star = Star(user=author, contract=contract)
        rating = Rating(user=author, contract=contract, score=5, note="Useful baseline.")
        target = PlaygroundTarget(
            user=author,
            label="Sandbox",
            playground_id="playground-123",
            is_default=True,
        )
        deployment = DeploymentHistory(
            user=author,
            contract_version=version,
            playground_target=target,
            playground_id="playground-123",
            status=DeploymentStatus.ACCEPTED,
            transport=DeploymentTransport.HTTP,
            request_payload={"contract": {"slug": "escrow"}},
            response_payload={"status": "accepted"},
        )

        session.add_all(
            [
                category,
                category_link,
                relation,
                star,
                rating,
                target,
                deployment,
            ]
        )
        session.commit()

        audit_log = AdminAuditLog(
            admin_user=author,
            action="publish",
            entity_type="contract_version",
            entity_id=version.id,
            summary="Published escrow v1.0.0",
            details={"contract_slug": contract.slug, "version": version.semantic_version},
        )
        session.add(audit_log)
        session.commit()

        stored_contract = session.exec(select(Contract).where(Contract.slug == "escrow")).one()
        stored_user = session.exec(select(User).where(User.email == "alice@example.com")).one()

        assert stored_user.profile is not None
        assert stored_user.profile.username == "alice"
        assert stored_contract.latest_published_version is not None
        assert stored_contract.latest_published_version.semantic_version == "1.0.0"
        assert stored_contract.category_links[0].category.slug == "finance"
        assert stored_contract.outgoing_relations[0].target_contract.slug == "token"
        assert stored_contract.stars[0].user.email == "alice@example.com"
        assert stored_contract.ratings[0].score == 5
        assert stored_contract.tags == ["finance", "escrow"]
        assert stored_contract.versions[0].deployments[0].status == DeploymentStatus.ACCEPTED
        assert stored_user.admin_actions[0].action == "publish"


def test_schema_enforces_single_star_per_user_and_contract() -> None:
    engine = _build_engine()

    with Session(engine) as session:
        user = User(email="bob@example.com", password_hash="hashed-password")
        contract = Contract(
            slug="vault",
            contract_name="con_vault",
            display_name="Vault",
            short_summary="Vault example.",
            long_description="Long-form description for the vault contract.",
        )

        session.add_all([user, contract])
        session.commit()

        session.add(Star(user_id=user.id, contract_id=contract.id))
        session.commit()
        session.add(Star(user_id=user.id, contract_id=contract.id))

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Expected duplicate star insert to fail")
