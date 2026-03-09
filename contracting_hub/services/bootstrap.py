"""Local development bootstrap helpers for reference catalog data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import sqlalchemy as sa
from sqlmodel import Session, select

from contracting_hub.config import AppSettings, get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import Category, Profile, User, UserRole


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
class BootstrapSeedReport:
    """Summary of changes applied during a local bootstrap run."""

    schema_ready: bool
    categories_created: int
    categories_existing: int
    admin_created: bool
    admin_promoted: bool
    profile_created: bool
    warnings: tuple[str, ...] = ()


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


def _schema_ready(session: Session) -> bool:
    """Return whether the required tables exist for bootstrap inserts."""
    bind = session.get_bind()
    inspector = sa.inspect(bind)
    return REQUIRED_SCHEMA_TABLES.issubset(set(inspector.get_table_names()))


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


def seed_local_development_data(
    *,
    settings: AppSettings | None = None,
    session: Session | None = None,
) -> BootstrapSeedReport:
    """Seed reference categories and the bootstrap admin into the current database."""
    resolved_settings = settings or get_settings()

    if session is None:
        with session_scope() as managed_session:
            return seed_local_development_data(settings=resolved_settings, session=managed_session)

    if not _schema_ready(session):
        return BootstrapSeedReport(
            schema_ready=False,
            categories_created=0,
            categories_existing=0,
            admin_created=False,
            admin_promoted=False,
            profile_created=False,
            warnings=("Local bootstrap skipped because the schema has not been migrated yet.",),
        )

    categories_created, categories_existing, category_warnings = _seed_categories(session)
    admin_created, admin_promoted, profile_created, admin_warnings = _seed_bootstrap_admin(
        session,
        definition=build_bootstrap_admin_definition(resolved_settings),
    )
    session.commit()

    return BootstrapSeedReport(
        schema_ready=True,
        categories_created=categories_created,
        categories_existing=categories_existing,
        admin_created=admin_created,
        admin_promoted=admin_promoted,
        profile_created=profile_created,
        warnings=tuple(category_warnings + admin_warnings),
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
    lines.extend(f"warning={warning}" for warning in report.warnings)
    return "\n".join(lines)


def main() -> int:
    """Seed the configured local database and print a concise summary."""
    report = seed_local_development_data()
    print(_format_bootstrap_report(report))
    return 0 if report.schema_ready else 1


__all__ = [
    "BootstrapAdminDefinition",
    "BootstrapSeedReport",
    "CategorySeedDefinition",
    "DEFAULT_CATEGORY_TAXONOMY",
    "REQUIRED_SCHEMA_TABLES",
    "build_bootstrap_admin_definition",
    "main",
    "seed_local_development_data",
]


if __name__ == "__main__":
    raise SystemExit(main())
