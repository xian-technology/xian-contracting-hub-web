"""Local development bootstrap helpers for reference catalog data."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final

import sqlalchemy as sa
from sqlmodel import Session, select

from contracting_hub.config import AppSettings, get_settings
from contracting_hub.database import session_scope
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
from contracting_hub.services.auth import hash_password
from contracting_hub.services.contract_versions import create_contract_version


@dataclass(frozen=True)
class CategorySeedDefinition:
    """Reference category metadata inserted into local development databases."""

    slug: str
    name: str
    description: str
    sort_order: int


@dataclass(frozen=True)
class BootstrapAdminDefinition:
    """Seed data for the default local administrator account."""

    email: str
    username: str
    display_name: str | None
    password_hash: str


@dataclass(frozen=True)
class DemoUserSeedDefinition:
    """Reference local account used by the demo catalog."""

    email: str
    username: str
    display_name: str
    role: UserRole
    bio: str | None = None
    website_url: str | None = None
    github_url: str | None = None
    xian_profile_url: str | None = None


@dataclass(frozen=True)
class DemoVersionSeedDefinition:
    """Immutable version snapshot inserted for one demo contract."""

    semantic_version: str
    source_code: str
    changelog: str
    status: PublicationStatus
    published_at: datetime | None = None


@dataclass(frozen=True)
class DemoContractSeedDefinition:
    """Reference contract catalog entry used for local QA and development."""

    slug: str
    contract_name: str
    display_name: str
    short_summary: str
    long_description: str
    status: PublicationStatus
    primary_category_slug: str
    created_at: datetime
    updated_at: datetime
    versions: tuple[DemoVersionSeedDefinition, ...]
    author_email: str | None = None
    author_label: str | None = None
    featured: bool = False
    license_name: str | None = None
    documentation_url: str | None = None
    source_repository_url: str | None = None
    network: ContractNetwork | None = None
    tags: tuple[str, ...] = ()
    secondary_category_slugs: tuple[str, ...] = ()


@dataclass(frozen=True)
class DemoRelationSeedDefinition:
    """Typed relation inserted between two demo contracts."""

    source_slug: str
    target_slug: str
    relation_type: ContractRelationType
    note: str | None = None


@dataclass(frozen=True)
class DemoStarSeedDefinition:
    """One demo star/favorite edge."""

    user_email: str
    contract_slug: str


@dataclass(frozen=True)
class DemoRatingSeedDefinition:
    """One demo rating entry."""

    user_email: str
    contract_slug: str
    score: int
    note: str | None = None


@dataclass(frozen=True)
class DemoPlaygroundTargetSeedDefinition:
    """Saved playground target inserted for one demo user."""

    user_email: str
    label: str
    playground_id: str
    is_default: bool = False
    last_used_at: datetime | None = None


@dataclass(frozen=True)
class DemoDeploymentSeedDefinition:
    """Recorded deployment attempt inserted for the demo catalog."""

    user_email: str
    contract_slug: str
    semantic_version: str
    playground_id: str
    status: DeploymentStatus
    initiated_at: datetime
    external_request_id: str
    request_payload: dict[str, object]
    transport: DeploymentTransport | None = None
    completed_at: datetime | None = None
    redirect_url: str | None = None
    response_payload: dict[str, object] | None = None
    error_payload: dict[str, object] | None = None
    playground_target_playground_id: str | None = None


@dataclass(frozen=True)
class DemoAuditLogSeedDefinition:
    """Admin audit activity inserted for local QA."""

    admin_email: str
    action: str
    entity_type: str
    entity_slug: str
    summary: str
    details: dict[str, object]
    semantic_version: str | None = None


@dataclass(frozen=True)
class DemoSeedReport:
    """Summary of demo catalog records created during one local seed run."""

    schema_ready: bool
    users_created: int
    profiles_created: int
    contracts_created: int
    versions_created: int
    relations_created: int
    stars_created: int
    ratings_created: int
    playground_targets_created: int
    deployments_created: int
    audit_logs_created: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BootstrapSeedReport:
    """Summary of changes applied during a local bootstrap run."""

    schema_ready: bool
    categories_created: int
    categories_existing: int
    admin_created: bool
    admin_promoted: bool
    profile_created: bool
    warnings: tuple[str, ...] = ()
    demo_report: DemoSeedReport | None = None


def _demo_timestamp(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 2, day, hour, 0, tzinfo=timezone.utc)


DEFAULT_CATEGORY_TAXONOMY: Final[tuple[CategorySeedDefinition, ...]] = (
    CategorySeedDefinition(
        slug="tokens",
        name="Tokens",
        description="Fungible token contracts, minting logic, and supply primitives.",
        sort_order=10,
    ),
    CategorySeedDefinition(
        slug="nfts",
        name="NFTs",
        description="Non-fungible token, collectible, and on-chain asset patterns.",
        sort_order=20,
    ),
    CategorySeedDefinition(
        slug="defi",
        name="DeFi",
        description="Vaults, lending, liquidity, and treasury-oriented contract flows.",
        sort_order=30,
    ),
    CategorySeedDefinition(
        slug="governance",
        name="Governance",
        description="DAO voting, proposal execution, and protocol control modules.",
        sort_order=40,
    ),
    CategorySeedDefinition(
        slug="marketplaces",
        name="Marketplaces",
        description="Exchange, auction, and payment-settlement contract patterns.",
        sort_order=50,
    ),
    CategorySeedDefinition(
        slug="identity",
        name="Identity",
        description="Profile, reputation, registry, and access-control building blocks.",
        sort_order=60,
    ),
    CategorySeedDefinition(
        slug="oracles",
        name="Oracles",
        description="Data-ingestion and off-chain coordination helpers for Xian apps.",
        sort_order=70,
    ),
    CategorySeedDefinition(
        slug="utilities",
        name="Utilities",
        description="Shared helpers, standards support, and operational infrastructure.",
        sort_order=80,
    ),
    CategorySeedDefinition(
        slug="gaming",
        name="Gaming",
        description="Game mechanics, reward loops, and interactive on-chain systems.",
        sort_order=90,
    ),
    CategorySeedDefinition(
        slug="examples",
        name="Examples",
        description="Educational reference contracts and smaller implementation samples.",
        sort_order=100,
    ),
)
REQUIRED_SCHEMA_TABLES: Final[frozenset[str]] = frozenset({"categories", "profiles", "users"})
REQUIRED_DEMO_SCHEMA_TABLES: Final[frozenset[str]] = frozenset(
    {
        "admin_audit_logs",
        "categories",
        "contract_category_links",
        "contract_relations",
        "contract_versions",
        "contracts",
        "deployment_history",
        "playground_targets",
        "profiles",
        "ratings",
        "stars",
        "users",
    }
)
DEFAULT_LOCAL_DEMO_PASSWORD = "secret-password"
DEMO_USER_DEFINITIONS: Final[tuple[DemoUserSeedDefinition, ...]] = (
    DemoUserSeedDefinition(
        email="catalog-admin@example.com",
        username="catalogadmin",
        display_name="Catalog Admin",
        role=UserRole.ADMIN,
        bio="Runs release checks and curates the featured Xian catalog.",
        website_url="https://contractinghub.local/admin",
        github_url="https://github.com/xian-labs",
    ),
    DemoUserSeedDefinition(
        email="alice@example.com",
        username="alice",
        display_name="Alice Validator",
        role=UserRole.USER,
        bio="Builds reusable escrow and settlement releases for treasury teams.",
        website_url="https://alice.dev",
        github_url="https://github.com/alice",
        xian_profile_url="https://xian.org/u/alice",
    ),
    DemoUserSeedDefinition(
        email="bob@example.com",
        username="bob",
        display_name="Bob Review",
        role=UserRole.USER,
        bio="Ships oracle and data-ingestion helpers for the Xian sandbox.",
        github_url="https://github.com/bob-review",
    ),
    DemoUserSeedDefinition(
        email="charlie@example.com",
        username="charlie",
        display_name="Charlie Curator",
        role=UserRole.USER,
        bio="Maintains governance examples and curates educational contract samples.",
        github_url="https://github.com/charlie-curator",
    ),
)
DEMO_CONTRACT_DEFINITIONS: Final[tuple[DemoContractSeedDefinition, ...]] = (
    DemoContractSeedDefinition(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Curated escrow settlement primitives for staged payouts.",
        long_description=(
            "Production-style escrow settlement contract with version history, "
            "deployment records, ratings, and related utility references."
        ),
        author_email="alice@example.com",
        status=PublicationStatus.PUBLISHED,
        featured=True,
        license_name="MIT",
        documentation_url="https://docs.example.com/escrow",
        source_repository_url="https://github.com/example/escrow",
        network=ContractNetwork.SANDBOX,
        tags=("escrow", "settlement"),
        primary_category_slug="defi",
        secondary_category_slugs=("utilities",),
        created_at=_demo_timestamp(2),
        updated_at=_demo_timestamp(9),
        versions=(
            DemoVersionSeedDefinition(
                semantic_version="1.0.0",
                source_code="@export\ndef settle_release_path():\n    return 'legacy escrow'\n",
                changelog="Legacy public release.",
                status=PublicationStatus.DEPRECATED,
                published_at=_demo_timestamp(3),
            ),
            DemoVersionSeedDefinition(
                semantic_version="1.1.0",
                source_code="@export\ndef settle_release_path():\n    return 'draft escrow'\n",
                changelog="Draft release used for version-manager preview coverage.",
                status=PublicationStatus.DRAFT,
            ),
            DemoVersionSeedDefinition(
                semantic_version="2.0.0",
                source_code="@export\ndef settle_release_path():\n    return 'released escrow'\n",
                changelog="Current public release.",
                status=PublicationStatus.PUBLISHED,
                published_at=_demo_timestamp(9),
            ),
        ),
    ),
    DemoContractSeedDefinition(
        slug="vault",
        contract_name="con_vault",
        display_name="Vault",
        short_summary="Treasury vault reference for shared operational flows.",
        long_description=(
            "Security-focused custody helper that pairs with escrow and oracle "
            "examples across the demo catalog."
        ),
        author_label="Core Team",
        status=PublicationStatus.PUBLISHED,
        featured=True,
        license_name="Apache-2.0",
        documentation_url="https://docs.example.com/vault",
        source_repository_url="https://github.com/example/vault",
        network=ContractNetwork.MAINNET_COMPATIBLE,
        tags=("treasury", "security"),
        primary_category_slug="defi",
        secondary_category_slugs=("utilities",),
        created_at=_demo_timestamp(4),
        updated_at=_demo_timestamp(8),
        versions=(
            DemoVersionSeedDefinition(
                semantic_version="1.0.0",
                source_code="@export\ndef treasury_guard_marker():\n    return 'vault'\n",
                changelog="Initial vault release.",
                status=PublicationStatus.PUBLISHED,
                published_at=_demo_timestamp(6),
            ),
        ),
    ),
    DemoContractSeedDefinition(
        slug="price-oracle",
        contract_name="con_price_oracle",
        display_name="Price Oracle",
        short_summary="Sandbox oracle contract with a public release history.",
        long_description=(
            "Oracle feed adapter that demonstrates multiple public releases, "
            "deployment history, and author leaderboard coverage."
        ),
        author_email="bob@example.com",
        status=PublicationStatus.PUBLISHED,
        documentation_url="https://docs.example.com/price-oracle",
        source_repository_url="https://github.com/example/price-oracle",
        network=ContractNetwork.TESTNET,
        tags=("oracle", "feeds"),
        primary_category_slug="oracles",
        secondary_category_slugs=("utilities",),
        created_at=_demo_timestamp(5),
        updated_at=_demo_timestamp(10),
        versions=(
            DemoVersionSeedDefinition(
                semantic_version="0.9.0",
                source_code="@export\ndef price_feed_symbol():\n    return 'legacy price feed'\n",
                changelog="Deprecated sandbox release.",
                status=PublicationStatus.DEPRECATED,
                published_at=_demo_timestamp(5),
            ),
            DemoVersionSeedDefinition(
                semantic_version="1.0.0",
                source_code="@export\ndef price_feed_symbol():\n    return 'xian/usd'\n",
                changelog="Stable public release for sandbox deployments.",
                status=PublicationStatus.PUBLISHED,
                published_at=_demo_timestamp(10),
            ),
        ),
    ),
    DemoContractSeedDefinition(
        slug="governance-toolkit",
        contract_name="con_governance_toolkit",
        display_name="Governance Toolkit",
        short_summary="Deprecated governance helper kept for version and admin QA.",
        long_description=(
            "Older governance utility retained in the catalog to exercise deprecated "
            "badges, public visibility, and leaderboard scoring."
        ),
        author_email="charlie@example.com",
        status=PublicationStatus.DEPRECATED,
        tags=("governance", "voting"),
        primary_category_slug="governance",
        created_at=_demo_timestamp(1),
        updated_at=_demo_timestamp(7),
        versions=(
            DemoVersionSeedDefinition(
                semantic_version="1.0.0",
                source_code=(
                    "@export\ndef governance_snapshot_label():\n    return 'governance toolkit'\n"
                ),
                changelog="Deprecated but still accessible public release.",
                status=PublicationStatus.DEPRECATED,
                published_at=_demo_timestamp(7),
            ),
        ),
    ),
    DemoContractSeedDefinition(
        slug="market-maker-legacy",
        contract_name="con_market_maker_legacy",
        display_name="Market Maker Legacy",
        short_summary="Archived market helper preserved for admin catalog coverage.",
        long_description=(
            "Archived sample that keeps admin archive filters, audit logs, and "
            "content-operations empty states from going blank in development."
        ),
        author_label="Core Team",
        status=PublicationStatus.ARCHIVED,
        tags=("market", "archive"),
        primary_category_slug="marketplaces",
        created_at=_demo_timestamp(2),
        updated_at=_demo_timestamp(6),
        versions=(
            DemoVersionSeedDefinition(
                semantic_version="0.9.0",
                source_code="@export\ndef market_maker_mode():\n    return 'legacy market maker'\n",
                changelog="Previously public archived release.",
                status=PublicationStatus.PUBLISHED,
                published_at=_demo_timestamp(4),
            ),
        ),
    ),
    DemoContractSeedDefinition(
        slug="faucet-playground",
        contract_name="con_faucet_playground",
        display_name="Faucet Playground",
        short_summary="Draft-only faucet example kept for admin version workflows.",
        long_description=(
            "Draft example contract used to exercise admin editing, preview diffs, "
            "and unpublished-content guards."
        ),
        author_email="catalog-admin@example.com",
        status=PublicationStatus.DRAFT,
        tags=("example", "faucet"),
        primary_category_slug="examples",
        created_at=_demo_timestamp(8),
        updated_at=_demo_timestamp(11),
        versions=(
            DemoVersionSeedDefinition(
                semantic_version="0.1.0",
                source_code="@export\ndef playground_faucet_label():\n    return 'draft faucet'\n",
                changelog="Draft example release.",
                status=PublicationStatus.DRAFT,
            ),
        ),
    ),
)
DEMO_RELATION_DEFINITIONS: Final[tuple[DemoRelationSeedDefinition, ...]] = (
    DemoRelationSeedDefinition(
        source_slug="escrow",
        target_slug="vault",
        relation_type=ContractRelationType.COMPANION,
    ),
    DemoRelationSeedDefinition(
        source_slug="price-oracle",
        target_slug="vault",
        relation_type=ContractRelationType.DEPENDS_ON,
    ),
    DemoRelationSeedDefinition(
        source_slug="faucet-playground",
        target_slug="escrow",
        relation_type=ContractRelationType.EXAMPLE_FOR,
    ),
)
DEMO_STAR_DEFINITIONS: Final[tuple[DemoStarSeedDefinition, ...]] = (
    DemoStarSeedDefinition(user_email="bob@example.com", contract_slug="escrow"),
    DemoStarSeedDefinition(user_email="charlie@example.com", contract_slug="escrow"),
    DemoStarSeedDefinition(user_email="catalog-admin@example.com", contract_slug="escrow"),
    DemoStarSeedDefinition(user_email="alice@example.com", contract_slug="vault"),
    DemoStarSeedDefinition(user_email="bob@example.com", contract_slug="vault"),
    DemoStarSeedDefinition(user_email="charlie@example.com", contract_slug="vault"),
    DemoStarSeedDefinition(user_email="alice@example.com", contract_slug="price-oracle"),
    DemoStarSeedDefinition(user_email="catalog-admin@example.com", contract_slug="price-oracle"),
)
DEMO_RATING_DEFINITIONS: Final[tuple[DemoRatingSeedDefinition, ...]] = (
    DemoRatingSeedDefinition(
        user_email="bob@example.com",
        contract_slug="escrow",
        score=5,
        note="Stable enough for treasury review.",
    ),
    DemoRatingSeedDefinition(
        user_email="charlie@example.com",
        contract_slug="escrow",
        score=4,
        note="Strong example with a clean upgrade path.",
    ),
    DemoRatingSeedDefinition(
        user_email="alice@example.com",
        contract_slug="vault",
        score=5,
        note="Reliable custody helper.",
    ),
    DemoRatingSeedDefinition(
        user_email="catalog-admin@example.com",
        contract_slug="price-oracle",
        score=4,
        note="Good sandbox release for demo deployments.",
    ),
)
DEMO_PLAYGROUND_TARGET_DEFINITIONS: Final[tuple[DemoPlaygroundTargetSeedDefinition, ...]] = (
    DemoPlaygroundTargetSeedDefinition(
        user_email="alice@example.com",
        label="Alice Sandbox",
        playground_id="alice-sandbox",
        is_default=True,
        last_used_at=_demo_timestamp(10, hour=14),
    ),
    DemoPlaygroundTargetSeedDefinition(
        user_email="alice@example.com",
        label="Treasury QA",
        playground_id="alice-treasury",
        last_used_at=_demo_timestamp(9, hour=16),
    ),
    DemoPlaygroundTargetSeedDefinition(
        user_email="bob@example.com",
        label="Oracle Bench",
        playground_id="bob-oracle",
        is_default=True,
        last_used_at=_demo_timestamp(10, hour=11),
    ),
)
DEMO_DEPLOYMENT_DEFINITIONS: Final[tuple[DemoDeploymentSeedDefinition, ...]] = (
    DemoDeploymentSeedDefinition(
        user_email="alice@example.com",
        contract_slug="escrow",
        semantic_version="2.0.0",
        playground_id="alice-sandbox",
        playground_target_playground_id="alice-sandbox",
        status=DeploymentStatus.REDIRECT_REQUIRED,
        transport=DeploymentTransport.DEEP_LINK,
        initiated_at=_demo_timestamp(10, hour=14),
        completed_at=_demo_timestamp(10, hour=14),
        external_request_id="demo-escrow-redirect",
        redirect_url=(
            "https://playground.local/deploy?playground_id=alice-sandbox&contract=con_escrow"
        ),
        request_payload={
            "playground_id": "alice-sandbox",
            "contract_slug": "escrow",
            "semantic_version": "2.0.0",
        },
        response_payload={
            "message": "Redirect the user to the playground.",
            "status": "redirect_required",
        },
    ),
    DemoDeploymentSeedDefinition(
        user_email="alice@example.com",
        contract_slug="vault",
        semantic_version="1.0.0",
        playground_id="alice-treasury",
        playground_target_playground_id="alice-treasury",
        status=DeploymentStatus.ACCEPTED,
        transport=DeploymentTransport.HTTP,
        initiated_at=_demo_timestamp(9, hour=16),
        completed_at=_demo_timestamp(9, hour=16),
        external_request_id="demo-vault-accepted",
        request_payload={
            "playground_id": "alice-treasury",
            "contract_slug": "vault",
            "semantic_version": "1.0.0",
        },
        response_payload={
            "message": "Deployment accepted by the playground adapter.",
            "status": "accepted",
        },
    ),
    DemoDeploymentSeedDefinition(
        user_email="bob@example.com",
        contract_slug="price-oracle",
        semantic_version="1.0.0",
        playground_id="bob-oracle",
        playground_target_playground_id="bob-oracle",
        status=DeploymentStatus.FAILED,
        transport=DeploymentTransport.HTTP,
        initiated_at=_demo_timestamp(10, hour=11),
        completed_at=_demo_timestamp(10, hour=11),
        external_request_id="demo-oracle-failed",
        request_payload={
            "playground_id": "bob-oracle",
            "contract_slug": "price-oracle",
            "semantic_version": "1.0.0",
        },
        error_payload={
            "code": "adapter_timeout",
            "message": "The playground did not confirm the deployment request in time.",
        },
    ),
)
DEMO_AUDIT_LOG_DEFINITIONS: Final[tuple[DemoAuditLogSeedDefinition, ...]] = (
    DemoAuditLogSeedDefinition(
        admin_email="catalog-admin@example.com",
        action="create_contract",
        entity_type="contract",
        entity_slug="faucet-playground",
        summary="Created draft faucet example contract.",
        details={"contract_slug": "faucet-playground"},
    ),
    DemoAuditLogSeedDefinition(
        admin_email="catalog-admin@example.com",
        action="publish_version",
        entity_type="contract_version",
        entity_slug="escrow",
        summary="Published escrow 2.0.0.",
        details={"contract_slug": "escrow", "semantic_version": "2.0.0"},
        semantic_version="2.0.0",
    ),
    DemoAuditLogSeedDefinition(
        admin_email="catalog-admin@example.com",
        action="archive_contract",
        entity_type="contract",
        entity_slug="market-maker-legacy",
        summary="Archived the legacy market maker sample.",
        details={"contract_slug": "market-maker-legacy"},
    ),
)


def build_bootstrap_admin_definition(
    settings: AppSettings | None = None,
) -> BootstrapAdminDefinition | None:
    """Return the configured bootstrap admin seed or disable it when incomplete."""
    resolved_settings = settings or get_settings()
    if (
        resolved_settings.bootstrap_admin_email is None
        or resolved_settings.bootstrap_admin_username is None
    ):
        return None

    return BootstrapAdminDefinition(
        email=resolved_settings.bootstrap_admin_email,
        username=resolved_settings.bootstrap_admin_username,
        display_name=resolved_settings.bootstrap_admin_display_name,
        password_hash=resolved_settings.bootstrap_admin_password_hash,
    )


def _schema_ready(
    session: Session,
    *,
    required_tables: frozenset[str] = REQUIRED_SCHEMA_TABLES,
) -> bool:
    """Return whether the required tables exist for bootstrap inserts."""
    bind = session.get_bind()
    inspector = sa.inspect(bind)
    return required_tables.issubset(set(inspector.get_table_names()))


def _seed_categories(session: Session) -> tuple[int, int, list[str]]:
    """Insert missing reference categories without overwriting existing rows."""
    existing_categories = session.exec(select(Category)).all()
    existing_slugs = {category.slug for category in existing_categories}
    existing_names = {category.name for category in existing_categories}
    created_count = 0
    warnings: list[str] = []

    for definition in DEFAULT_CATEGORY_TAXONOMY:
        if definition.slug in existing_slugs:
            continue
        if definition.name in existing_names:
            warnings.append(
                (
                    "Skipped bootstrap category "
                    f"{definition.slug!r} because the name {definition.name!r} already exists."
                )
            )
            continue

        session.add(
            Category(
                slug=definition.slug,
                name=definition.name,
                description=definition.description,
                sort_order=definition.sort_order,
            )
        )
        existing_slugs.add(definition.slug)
        existing_names.add(definition.name)
        created_count += 1

    return created_count, len(existing_categories), warnings


def _seed_bootstrap_admin(
    session: Session,
    *,
    definition: BootstrapAdminDefinition | None,
) -> tuple[bool, bool, bool, list[str]]:
    """Create or promote the configured bootstrap admin account."""
    if definition is None:
        return False, False, False, []

    warnings: list[str] = []
    profile_for_username = session.exec(
        select(Profile).where(Profile.username == definition.username)
    ).first()
    user = session.exec(select(User).where(User.email == definition.email)).first()

    if user is None and profile_for_username is not None:
        warnings.append(
            (
                "Skipped bootstrap admin creation because username "
                f"{definition.username!r} is already attached to another account."
            )
        )
        return False, False, False, warnings

    admin_created = False
    admin_promoted = False
    profile_created = False

    if user is None:
        user = User(
            email=definition.email,
            password_hash=definition.password_hash,
            role=UserRole.ADMIN,
        )
        user.profile = Profile(
            username=definition.username,
            display_name=definition.display_name,
        )
        session.add(user)
        return True, False, True, warnings

    if user.role is not UserRole.ADMIN:
        user.role = UserRole.ADMIN
        admin_promoted = True

    if user.profile is None:
        if profile_for_username is not None and profile_for_username.user_id != user.id:
            warnings.append(
                (
                    "Skipped bootstrap admin profile creation because username "
                    f"{definition.username!r} is already attached to another account."
                )
            )
        else:
            user.profile = Profile(
                username=definition.username,
                display_name=definition.display_name,
            )
            profile_created = True

    return admin_created, admin_promoted, profile_created, warnings


def _seed_demo_users(session: Session) -> tuple[dict[str, User], int, int, list[str]]:
    users_by_email = {user.email: user for user in session.exec(select(User)).all()}
    profiles_by_username = {
        profile.username: profile for profile in session.exec(select(Profile)).all()
    }
    users_created = 0
    profiles_created = 0
    warnings: list[str] = []

    for definition in DEMO_USER_DEFINITIONS:
        user = users_by_email.get(definition.email)
        profile_for_username = profiles_by_username.get(definition.username)

        if user is None and profile_for_username is not None:
            warnings.append(
                (
                    "Skipped demo user creation because username "
                    f"{definition.username!r} is already attached to another account."
                )
            )
            continue

        if user is None:
            user = User(
                email=definition.email,
                password_hash=hash_password(DEFAULT_LOCAL_DEMO_PASSWORD),
                role=definition.role,
            )
            user.profile = Profile(
                username=definition.username,
                display_name=definition.display_name,
                bio=definition.bio,
                website_url=definition.website_url,
                github_url=definition.github_url,
                xian_profile_url=definition.xian_profile_url,
            )
            session.add(user)
            users_by_email[definition.email] = user
            profiles_by_username[definition.username] = user.profile
            users_created += 1
            profiles_created += 1
            continue

        if user.profile is None:
            if profile_for_username is not None and profile_for_username.user_id != user.id:
                warnings.append(
                    (
                        "Skipped demo profile creation because username "
                        f"{definition.username!r} is already attached to another account."
                    )
                )
                continue

            user.profile = Profile(
                username=definition.username,
                display_name=definition.display_name,
                bio=definition.bio,
                website_url=definition.website_url,
                github_url=definition.github_url,
                xian_profile_url=definition.xian_profile_url,
            )
            profiles_by_username[definition.username] = user.profile
            profiles_created += 1

    session.flush()
    return users_by_email, users_created, profiles_created, warnings


def _seed_demo_contracts(
    session: Session,
    *,
    users_by_email: dict[str, User],
) -> tuple[dict[str, Contract], int, int, list[str]]:
    categories_by_slug = {
        category.slug: category
        for category in session.exec(select(Category).order_by(Category.sort_order)).all()
    }
    contracts_by_slug = {
        contract.slug: contract
        for contract in session.exec(select(Contract).order_by(Contract.id.asc())).all()
    }
    contracts_created = 0
    versions_created = 0
    warnings: list[str] = []

    for definition in DEMO_CONTRACT_DEFINITIONS:
        category_slugs = (definition.primary_category_slug, *definition.secondary_category_slugs)
        missing_category_slugs = [slug for slug in category_slugs if slug not in categories_by_slug]
        if missing_category_slugs:
            warnings.append(
                (
                    f"Skipped demo contract {definition.slug!r} because categories "
                    f"{', '.join(sorted(missing_category_slugs))!r} are missing."
                )
            )
            continue

        author_user_id = None
        if definition.author_email is not None:
            author = users_by_email.get(definition.author_email)
            if author is None or author.id is None:
                warnings.append(
                    (
                        f"Skipped demo contract {definition.slug!r} because author "
                        f"{definition.author_email!r} is unavailable."
                    )
                )
                continue
            author_user_id = author.id

        contract = contracts_by_slug.get(definition.slug)
        if contract is None:
            contract = Contract(
                slug=definition.slug,
                contract_name=definition.contract_name,
                display_name=definition.display_name,
                short_summary=definition.short_summary,
                long_description=definition.long_description,
                author_user_id=author_user_id,
                author_label=definition.author_label,
                status=definition.status,
                featured=definition.featured,
                license_name=definition.license_name,
                documentation_url=definition.documentation_url,
                source_repository_url=definition.source_repository_url,
                network=definition.network,
                tags=list(definition.tags),
                created_at=definition.created_at,
                updated_at=definition.updated_at,
            )
            contract.category_links = list(
                _build_demo_category_links(
                    categories_by_slug=categories_by_slug,
                    primary_category_slug=definition.primary_category_slug,
                    secondary_category_slugs=definition.secondary_category_slugs,
                )
            )
            session.add(contract)
            session.flush()
            contracts_by_slug[definition.slug] = contract
            contracts_created += 1

        existing_versions = {
            version.semantic_version
            for version in session.exec(
                select(ContractVersion).where(ContractVersion.contract_id == contract.id)
            ).all()
        }
        for version_definition in definition.versions:
            if version_definition.semantic_version in existing_versions:
                continue

            version = create_contract_version(
                session=session,
                contract_slug=definition.slug,
                semantic_version=version_definition.semantic_version,
                source_code=version_definition.source_code,
                changelog=version_definition.changelog,
                status=version_definition.status,
                published_at=version_definition.published_at,
                auto_commit=False,
            )
            version.created_at = version_definition.published_at or definition.updated_at
            version.updated_at = version_definition.published_at or definition.updated_at
            versions_created += 1
            existing_versions.add(version_definition.semantic_version)

        contract.created_at = definition.created_at
        contract.updated_at = definition.updated_at

    session.flush()
    return contracts_by_slug, contracts_created, versions_created, warnings


def _build_demo_category_links(
    *,
    categories_by_slug: dict[str, Category],
    primary_category_slug: str,
    secondary_category_slugs: tuple[str, ...],
) -> tuple[ContractCategoryLink, ...]:
    links = [
        ContractCategoryLink(
            category_id=_require_persisted_id(
                categories_by_slug[primary_category_slug].id,
                label="category",
            ),
            is_primary=True,
            sort_order=0,
        )
    ]
    for index, slug in enumerate(secondary_category_slugs, start=1):
        links.append(
            ContractCategoryLink(
                category_id=_require_persisted_id(categories_by_slug[slug].id, label="category"),
                is_primary=False,
                sort_order=index,
            )
        )
    return tuple(links)


def _seed_demo_relations(
    session: Session,
    *,
    contracts_by_slug: dict[str, Contract],
) -> tuple[int, list[str]]:
    existing_relations = {
        (relation.source_contract_id, relation.target_contract_id, relation.relation_type)
        for relation in session.exec(select(ContractRelation)).all()
    }
    created_count = 0
    warnings: list[str] = []

    for definition in DEMO_RELATION_DEFINITIONS:
        source_contract = contracts_by_slug.get(definition.source_slug)
        target_contract = contracts_by_slug.get(definition.target_slug)
        if source_contract is None or target_contract is None:
            warnings.append(
                (
                    "Skipped demo relation because one of the contracts is missing: "
                    f"{definition.source_slug!r} -> {definition.target_slug!r}."
                )
            )
            continue

        relation_key = (
            _require_persisted_id(source_contract.id, label="contract"),
            _require_persisted_id(target_contract.id, label="contract"),
            definition.relation_type,
        )
        if relation_key in existing_relations:
            continue

        session.add(
            ContractRelation(
                source_contract_id=relation_key[0],
                target_contract_id=relation_key[1],
                relation_type=definition.relation_type,
                note=definition.note,
            )
        )
        existing_relations.add(relation_key)
        created_count += 1

    return created_count, warnings


def _seed_demo_stars(
    session: Session,
    *,
    users_by_email: dict[str, User],
    contracts_by_slug: dict[str, Contract],
) -> tuple[int, list[str]]:
    existing_stars = {(star.user_id, star.contract_id) for star in session.exec(select(Star)).all()}
    created_count = 0
    warnings: list[str] = []

    for definition in DEMO_STAR_DEFINITIONS:
        user = users_by_email.get(definition.user_email)
        contract = contracts_by_slug.get(definition.contract_slug)
        if user is None or contract is None:
            warnings.append(
                (
                    "Skipped demo star because the user or contract is missing: "
                    f"{definition.user_email!r} -> {definition.contract_slug!r}."
                )
            )
            continue

        star_key = (
            _require_persisted_id(user.id, label="user"),
            _require_persisted_id(contract.id, label="contract"),
        )
        if star_key in existing_stars:
            continue

        session.add(Star(user_id=star_key[0], contract_id=star_key[1]))
        existing_stars.add(star_key)
        created_count += 1

    return created_count, warnings


def _seed_demo_ratings(
    session: Session,
    *,
    users_by_email: dict[str, User],
    contracts_by_slug: dict[str, Contract],
) -> tuple[int, list[str]]:
    existing_ratings = {
        (rating.user_id, rating.contract_id) for rating in session.exec(select(Rating)).all()
    }
    created_count = 0
    warnings: list[str] = []

    for definition in DEMO_RATING_DEFINITIONS:
        user = users_by_email.get(definition.user_email)
        contract = contracts_by_slug.get(definition.contract_slug)
        if user is None or contract is None:
            warnings.append(
                (
                    "Skipped demo rating because the user or contract is missing: "
                    f"{definition.user_email!r} -> {definition.contract_slug!r}."
                )
            )
            continue

        rating_key = (
            _require_persisted_id(user.id, label="user"),
            _require_persisted_id(contract.id, label="contract"),
        )
        if rating_key in existing_ratings:
            continue

        session.add(
            Rating(
                user_id=rating_key[0],
                contract_id=rating_key[1],
                score=definition.score,
                note=definition.note,
            )
        )
        existing_ratings.add(rating_key)
        created_count += 1

    return created_count, warnings


def _seed_demo_playground_targets(
    session: Session,
    *,
    users_by_email: dict[str, User],
) -> tuple[dict[tuple[str, str], PlaygroundTarget], int, list[str]]:
    existing_targets = session.exec(select(PlaygroundTarget)).all()
    targets_by_key = {
        (target.user.email, target.playground_id): target
        for target in existing_targets
        if target.user is not None
    }
    created_count = 0
    warnings: list[str] = []

    for definition in DEMO_PLAYGROUND_TARGET_DEFINITIONS:
        user = users_by_email.get(definition.user_email)
        if user is None:
            warnings.append(
                (
                    "Skipped demo playground target because the user is missing: "
                    f"{definition.user_email!r}."
                )
            )
            continue

        target_key = (definition.user_email, definition.playground_id)
        if target_key in targets_by_key:
            continue

        target = PlaygroundTarget(
            user_id=_require_persisted_id(user.id, label="user"),
            label=definition.label,
            playground_id=definition.playground_id,
            is_default=definition.is_default,
            last_used_at=definition.last_used_at,
        )
        session.add(target)
        session.flush()
        targets_by_key[target_key] = target
        created_count += 1

    return targets_by_key, created_count, warnings


def _seed_demo_deployments(
    session: Session,
    *,
    users_by_email: dict[str, User],
    contracts_by_slug: dict[str, Contract],
    targets_by_key: dict[tuple[str, str], PlaygroundTarget],
) -> tuple[int, list[str]]:
    existing_request_ids = {
        deployment.external_request_id
        for deployment in session.exec(select(DeploymentHistory)).all()
        if deployment.external_request_id is not None
    }
    created_count = 0
    warnings: list[str] = []

    for definition in DEMO_DEPLOYMENT_DEFINITIONS:
        if definition.external_request_id in existing_request_ids:
            continue

        user = users_by_email.get(definition.user_email)
        contract = contracts_by_slug.get(definition.contract_slug)
        if user is None or contract is None:
            warnings.append(
                (
                    "Skipped demo deployment because the user or contract is missing: "
                    f"{definition.user_email!r} -> {definition.contract_slug!r}."
                )
            )
            continue

        version = session.exec(
            select(ContractVersion).where(
                ContractVersion.contract_id == contract.id,
                ContractVersion.semantic_version == definition.semantic_version,
            )
        ).first()
        if version is None:
            warnings.append(
                (
                    f"Skipped demo deployment for {definition.contract_slug!r} because "
                    f"version {definition.semantic_version!r} is missing."
                )
            )
            continue

        target_id = None
        if definition.playground_target_playground_id is not None:
            target = targets_by_key.get(
                (definition.user_email, definition.playground_target_playground_id)
            )
            if target is None:
                warnings.append(
                    (
                        "Skipped demo deployment because the saved playground target is "
                        f"missing: {definition.playground_target_playground_id!r}."
                    )
                )
                continue
            target_id = _require_persisted_id(target.id, label="playground target")
            if target.last_used_at is None or (
                definition.completed_at is not None
                and target.last_used_at < definition.completed_at
            ):
                target.last_used_at = definition.completed_at

        session.add(
            DeploymentHistory(
                user_id=_require_persisted_id(user.id, label="user"),
                contract_version_id=_require_persisted_id(version.id, label="contract version"),
                playground_target_id=target_id,
                playground_id=definition.playground_id,
                status=definition.status,
                transport=definition.transport,
                external_request_id=definition.external_request_id,
                redirect_url=definition.redirect_url,
                request_payload=definition.request_payload,
                response_payload=definition.response_payload,
                error_payload=definition.error_payload,
                initiated_at=definition.initiated_at,
                completed_at=definition.completed_at,
            )
        )
        existing_request_ids.add(definition.external_request_id)
        created_count += 1

    return created_count, warnings


def _seed_demo_audit_logs(
    session: Session,
    *,
    users_by_email: dict[str, User],
    contracts_by_slug: dict[str, Contract],
) -> tuple[int, list[str]]:
    existing_log_keys = {
        (
            log.admin_user_id,
            log.action,
            log.entity_type,
            log.entity_id,
            log.summary,
        )
        for log in session.exec(select(AdminAuditLog)).all()
    }
    created_count = 0
    warnings: list[str] = []

    for definition in DEMO_AUDIT_LOG_DEFINITIONS:
        admin_user = users_by_email.get(definition.admin_email)
        contract = contracts_by_slug.get(definition.entity_slug)
        if admin_user is None or contract is None:
            warnings.append(
                (
                    "Skipped demo audit log because the admin or contract is missing: "
                    f"{definition.admin_email!r} -> {definition.entity_slug!r}."
                )
            )
            continue

        entity_id = _require_persisted_id(contract.id, label="contract")
        if definition.semantic_version is not None:
            version = session.exec(
                select(ContractVersion).where(
                    ContractVersion.contract_id == contract.id,
                    ContractVersion.semantic_version == definition.semantic_version,
                )
            ).first()
            if version is None:
                warnings.append(
                    (
                        "Skipped demo audit log because the contract version is missing: "
                        f"{definition.entity_slug!r} {definition.semantic_version!r}."
                    )
                )
                continue
            entity_id = _require_persisted_id(version.id, label="contract version")

        log_key = (
            _require_persisted_id(admin_user.id, label="admin user"),
            definition.action,
            definition.entity_type,
            entity_id,
            definition.summary,
        )
        if log_key in existing_log_keys:
            continue

        session.add(
            AdminAuditLog(
                admin_user_id=log_key[0],
                action=definition.action,
                entity_type=definition.entity_type,
                entity_id=log_key[3],
                summary=definition.summary,
                details=definition.details,
            )
        )
        existing_log_keys.add(log_key)
        created_count += 1

    return created_count, warnings


def _require_persisted_id(value: int | None, *, label: str) -> int:
    if value is None:
        raise RuntimeError(f"{label.title()} is missing a persisted identifier.")
    return value


def seed_demo_catalog_data(
    *,
    session: Session | None = None,
) -> DemoSeedReport:
    """Seed deterministic local demo users, contracts, engagement, and admin activity."""
    if session is None:
        with session_scope() as managed_session:
            return seed_demo_catalog_data(session=managed_session)

    if not _schema_ready(session, required_tables=REQUIRED_DEMO_SCHEMA_TABLES):
        return DemoSeedReport(
            schema_ready=False,
            users_created=0,
            profiles_created=0,
            contracts_created=0,
            versions_created=0,
            relations_created=0,
            stars_created=0,
            ratings_created=0,
            playground_targets_created=0,
            deployments_created=0,
            audit_logs_created=0,
            warnings=("Local demo seed skipped because the schema is not fully migrated yet.",),
        )

    users_by_email, users_created, profiles_created, user_warnings = _seed_demo_users(session)
    (
        contracts_by_slug,
        contracts_created,
        versions_created,
        contract_warnings,
    ) = _seed_demo_contracts(
        session,
        users_by_email=users_by_email,
    )
    relations_created, relation_warnings = _seed_demo_relations(
        session,
        contracts_by_slug=contracts_by_slug,
    )
    stars_created, star_warnings = _seed_demo_stars(
        session,
        users_by_email=users_by_email,
        contracts_by_slug=contracts_by_slug,
    )
    ratings_created, rating_warnings = _seed_demo_ratings(
        session,
        users_by_email=users_by_email,
        contracts_by_slug=contracts_by_slug,
    )
    targets_by_key, playground_targets_created, target_warnings = _seed_demo_playground_targets(
        session,
        users_by_email=users_by_email,
    )
    deployments_created, deployment_warnings = _seed_demo_deployments(
        session,
        users_by_email=users_by_email,
        contracts_by_slug=contracts_by_slug,
        targets_by_key=targets_by_key,
    )
    audit_logs_created, audit_log_warnings = _seed_demo_audit_logs(
        session,
        users_by_email=users_by_email,
        contracts_by_slug=contracts_by_slug,
    )
    session.commit()

    return DemoSeedReport(
        schema_ready=True,
        users_created=users_created,
        profiles_created=profiles_created,
        contracts_created=contracts_created,
        versions_created=versions_created,
        relations_created=relations_created,
        stars_created=stars_created,
        ratings_created=ratings_created,
        playground_targets_created=playground_targets_created,
        deployments_created=deployments_created,
        audit_logs_created=audit_logs_created,
        warnings=tuple(
            user_warnings
            + contract_warnings
            + relation_warnings
            + star_warnings
            + rating_warnings
            + target_warnings
            + deployment_warnings
            + audit_log_warnings
        ),
    )


def seed_local_development_data(
    *,
    settings: AppSettings | None = None,
    session: Session | None = None,
    include_demo_data: bool = False,
) -> BootstrapSeedReport:
    """Seed reference categories, bootstrap admin, and optional demo data."""
    resolved_settings = settings or get_settings()

    if session is None:
        with session_scope() as managed_session:
            return seed_local_development_data(
                settings=resolved_settings,
                session=managed_session,
                include_demo_data=include_demo_data,
            )

    if not _schema_ready(session):
        return BootstrapSeedReport(
            schema_ready=False,
            categories_created=0,
            categories_existing=0,
            admin_created=False,
            admin_promoted=False,
            profile_created=False,
            warnings=("Local bootstrap skipped because the schema has not been migrated yet.",),
            demo_report=None,
        )

    categories_created, categories_existing, category_warnings = _seed_categories(session)
    admin_created, admin_promoted, profile_created, admin_warnings = _seed_bootstrap_admin(
        session,
        definition=build_bootstrap_admin_definition(resolved_settings),
    )
    session.commit()

    demo_report = seed_demo_catalog_data(session=session) if include_demo_data else None
    warnings = list(category_warnings + admin_warnings)
    if demo_report is not None:
        warnings.extend(demo_report.warnings)

    return BootstrapSeedReport(
        schema_ready=True,
        categories_created=categories_created,
        categories_existing=categories_existing,
        admin_created=admin_created,
        admin_promoted=admin_promoted,
        profile_created=profile_created,
        warnings=tuple(warnings),
        demo_report=demo_report,
    )


def _format_bootstrap_report(report: BootstrapSeedReport) -> str:
    """Render a readable CLI summary for local bootstrap runs."""
    lines = [
        f"schema_ready={report.schema_ready}",
        f"categories_created={report.categories_created}",
        f"categories_existing={report.categories_existing}",
        f"admin_created={report.admin_created}",
        f"admin_promoted={report.admin_promoted}",
        f"profile_created={report.profile_created}",
    ]
    if report.demo_report is not None:
        lines.extend(
            [
                f"demo_schema_ready={report.demo_report.schema_ready}",
                f"demo_users_created={report.demo_report.users_created}",
                f"demo_profiles_created={report.demo_report.profiles_created}",
                f"demo_contracts_created={report.demo_report.contracts_created}",
                f"demo_versions_created={report.demo_report.versions_created}",
                f"demo_relations_created={report.demo_report.relations_created}",
                f"demo_stars_created={report.demo_report.stars_created}",
                f"demo_ratings_created={report.demo_report.ratings_created}",
                (
                    "demo_playground_targets_created="
                    f"{report.demo_report.playground_targets_created}"
                ),
                f"demo_deployments_created={report.demo_report.deployments_created}",
                f"demo_audit_logs_created={report.demo_report.audit_logs_created}",
                f"demo_login_password={DEFAULT_LOCAL_DEMO_PASSWORD}",
            ]
        )
        demo_admin = next(
            definition for definition in DEMO_USER_DEFINITIONS if definition.role is UserRole.ADMIN
        )
        lines.append(f"demo_admin_email={demo_admin.email}")
        lines.append(f"demo_admin_username={demo_admin.username}")
    lines.extend(f"warning={warning}" for warning in report.warnings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Seed the configured local database and print a concise summary."""
    parser = argparse.ArgumentParser(
        prog="python -m contracting_hub.services.bootstrap",
        description="Seed local bootstrap data into the configured database.",
    )
    parser.add_argument(
        "--demo-data",
        action="store_true",
        help="Seed the deterministic demo catalog on top of the base bootstrap data.",
    )
    args = parser.parse_args(argv)

    report = seed_local_development_data(include_demo_data=args.demo_data)
    print(_format_bootstrap_report(report))
    return 0 if report.schema_ready else 1


__all__ = [
    "BootstrapAdminDefinition",
    "BootstrapSeedReport",
    "CategorySeedDefinition",
    "DEFAULT_CATEGORY_TAXONOMY",
    "DEFAULT_LOCAL_DEMO_PASSWORD",
    "DEMO_CONTRACT_DEFINITIONS",
    "DEMO_USER_DEFINITIONS",
    "DemoContractSeedDefinition",
    "DemoSeedReport",
    "DemoUserSeedDefinition",
    "REQUIRED_DEMO_SCHEMA_TABLES",
    "REQUIRED_SCHEMA_TABLES",
    "build_bootstrap_admin_definition",
    "main",
    "seed_demo_catalog_data",
    "seed_local_development_data",
]


if __name__ == "__main__":
    raise SystemExit(main())
