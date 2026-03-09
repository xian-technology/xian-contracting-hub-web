"""Domain tables for the contracting hub catalog."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

import sqlalchemy as sa
import sqlmodel

from contracting_hub.models.base import TimestampedModel, utc_now


class UserRole(str, Enum):
    """Supported application roles."""

    USER = "user"
    ADMIN = "admin"


class UserStatus(str, Enum):
    """Supported account lifecycle states."""

    ACTIVE = "active"
    DISABLED = "disabled"


class PublicationStatus(str, Enum):
    """Shared publish-state values for contracts and versions."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class ContractRelationType(str, Enum):
    """Supported typed links between contracts."""

    DEPENDS_ON = "depends_on"
    COMPANION = "companion"
    EXAMPLE_FOR = "example_for"
    EXTENDS = "extends"
    SUPERSEDES = "supersedes"


class ContractNetwork(str, Enum):
    """Supported deployment target labels."""

    SANDBOX = "sandbox"
    TESTNET = "testnet"
    MAINNET_COMPATIBLE = "mainnet-compatible"


class LintStatus(str, Enum):
    """Summary states persisted for version lint runs."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class DeploymentStatus(str, Enum):
    """Lifecycle states for recorded deployment requests."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REDIRECT_REQUIRED = "redirect_required"
    FAILED = "failed"


class DeploymentTransport(str, Enum):
    """Transport labels emitted by playground adapters."""

    DEEP_LINK = "deep_link"
    HTTP = "http"
    HYBRID = "hybrid"


class User(TimestampedModel, table=True):
    """Authenticated application account."""

    __tablename__ = "users"

    email: str = sqlmodel.Field(max_length=320, unique=True, index=True)
    password_hash: str = sqlmodel.Field(max_length=255)
    role: UserRole = sqlmodel.Field(default=UserRole.USER, index=True)
    status: UserStatus = sqlmodel.Field(default=UserStatus.ACTIVE, index=True)
    last_login_at: datetime | None = sqlmodel.Field(default=None, index=True)

    profile: Optional["Profile"] = sqlmodel.Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "uselist": False},
    )
    authored_contracts: list["Contract"] = sqlmodel.Relationship(
        back_populates="author",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[Contract.author_user_id]",
        },
    )
    stars: list["Star"] = sqlmodel.Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    ratings: list["Rating"] = sqlmodel.Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    playground_targets: list["PlaygroundTarget"] = sqlmodel.Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    deployments: list["DeploymentHistory"] = sqlmodel.Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    admin_actions: list["AdminAuditLog"] = sqlmodel.Relationship(
        back_populates="admin_user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Profile(TimestampedModel, table=True):
    """Public-facing developer profile."""

    __tablename__ = "profiles"

    user_id: int = sqlmodel.Field(foreign_key="users.id", unique=True, index=True)
    username: str = sqlmodel.Field(max_length=32, unique=True, index=True)
    display_name: str | None = sqlmodel.Field(default=None, max_length=100)
    bio: str | None = sqlmodel.Field(default=None, max_length=1000)
    avatar_path: str | None = sqlmodel.Field(default=None, max_length=500)
    website_url: str | None = sqlmodel.Field(default=None, max_length=500)
    github_url: str | None = sqlmodel.Field(default=None, max_length=500)
    xian_profile_url: str | None = sqlmodel.Field(default=None, max_length=500)

    user: User = sqlmodel.Relationship(back_populates="profile")


class Category(TimestampedModel, table=True):
    """Browse taxonomy bucket for curated contracts."""

    __tablename__ = "categories"

    slug: str = sqlmodel.Field(max_length=64, unique=True, index=True)
    name: str = sqlmodel.Field(max_length=128, unique=True, index=True)
    description: str | None = sqlmodel.Field(default=None, max_length=512)
    sort_order: int = sqlmodel.Field(default=0, index=True)

    contract_links: list["ContractCategoryLink"] = sqlmodel.Relationship(
        back_populates="category",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Contract(TimestampedModel, table=True):
    """Stable catalog entry for a Xian contract."""

    __tablename__ = "contracts"

    slug: str = sqlmodel.Field(max_length=128, unique=True, index=True)
    contract_name: str = sqlmodel.Field(max_length=64, unique=True, index=True)
    display_name: str = sqlmodel.Field(max_length=128, index=True)
    short_summary: str = sqlmodel.Field(max_length=280)
    long_description: str = sqlmodel.Field(sa_column=sa.Column(sa.Text, nullable=False))
    author_user_id: int | None = sqlmodel.Field(default=None, foreign_key="users.id", index=True)
    author_label: str | None = sqlmodel.Field(default=None, max_length=128)
    status: PublicationStatus = sqlmodel.Field(default=PublicationStatus.DRAFT, index=True)
    featured: bool = sqlmodel.Field(default=False, index=True)
    license_name: str | None = sqlmodel.Field(default=None, max_length=64)
    documentation_url: str | None = sqlmodel.Field(default=None, max_length=500)
    source_repository_url: str | None = sqlmodel.Field(default=None, max_length=500)
    network: ContractNetwork | None = sqlmodel.Field(default=None, index=True)
    tags: list[str] = sqlmodel.Field(
        default_factory=list,
        sa_column=sa.Column(sa.JSON, nullable=False),
    )
    latest_published_version_id: int | None = sqlmodel.Field(
        default=None,
        foreign_key="contract_versions.id",
        index=True,
    )

    author: Optional[User] = sqlmodel.Relationship(
        back_populates="authored_contracts",
        sa_relationship_kwargs={"foreign_keys": "[Contract.author_user_id]"},
    )
    versions: list["ContractVersion"] = sqlmodel.Relationship(
        back_populates="contract",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[ContractVersion.contract_id]",
        },
    )
    latest_published_version: Optional["ContractVersion"] = sqlmodel.Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Contract.latest_published_version_id]",
            "post_update": True,
        },
    )
    category_links: list["ContractCategoryLink"] = sqlmodel.Relationship(
        back_populates="contract",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    outgoing_relations: list["ContractRelation"] = sqlmodel.Relationship(
        back_populates="source_contract",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[ContractRelation.source_contract_id]",
        },
    )
    incoming_relations: list["ContractRelation"] = sqlmodel.Relationship(
        back_populates="target_contract",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[ContractRelation.target_contract_id]",
        },
    )
    stars: list["Star"] = sqlmodel.Relationship(
        back_populates="contract",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    ratings: list["Rating"] = sqlmodel.Relationship(
        back_populates="contract",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ContractVersion(TimestampedModel, table=True):
    """Immutable source snapshot for a contract release."""

    __tablename__ = "contract_versions"
    __table_args__ = (
        sa.UniqueConstraint(
            "contract_id",
            "semantic_version",
            name="uq_contract_versions_contract_semantic_version",
        ),
    )

    contract_id: int = sqlmodel.Field(foreign_key="contracts.id", index=True)
    semantic_version: str = sqlmodel.Field(max_length=32, index=True)
    status: PublicationStatus = sqlmodel.Field(default=PublicationStatus.DRAFT, index=True)
    source_code: str = sqlmodel.Field(sa_column=sa.Column(sa.Text, nullable=False))
    source_hash_sha256: str = sqlmodel.Field(max_length=64, index=True)
    changelog: str | None = sqlmodel.Field(default=None, sa_column=sa.Column(sa.Text))
    previous_version_id: int | None = sqlmodel.Field(
        default=None,
        foreign_key="contract_versions.id",
        index=True,
    )
    lint_status: LintStatus | None = sqlmodel.Field(default=None, index=True)
    lint_summary: dict[str, Any] | None = sqlmodel.Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    lint_results: list[dict[str, Any]] | None = sqlmodel.Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    diff_summary: dict[str, Any] | None = sqlmodel.Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    published_at: datetime | None = sqlmodel.Field(default=None, index=True)

    contract: Contract = sqlmodel.Relationship(
        back_populates="versions",
        sa_relationship_kwargs={"foreign_keys": "[ContractVersion.contract_id]"},
    )
    previous_version: Optional["ContractVersion"] = sqlmodel.Relationship(
        back_populates="next_versions",
        sa_relationship_kwargs={
            "remote_side": "ContractVersion.id",
            "foreign_keys": "[ContractVersion.previous_version_id]",
        },
    )
    next_versions: list["ContractVersion"] = sqlmodel.Relationship(
        back_populates="previous_version",
        sa_relationship_kwargs={"foreign_keys": "[ContractVersion.previous_version_id]"},
    )
    deployments: list["DeploymentHistory"] = sqlmodel.Relationship(
        back_populates="contract_version",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ContractCategoryLink(TimestampedModel, table=True):
    """Join table for contract taxonomy links."""

    __tablename__ = "contract_category_links"
    __table_args__ = (
        sa.UniqueConstraint(
            "contract_id",
            "category_id",
            name="uq_contract_category_links_contract_category",
        ),
    )

    contract_id: int = sqlmodel.Field(foreign_key="contracts.id", index=True)
    category_id: int = sqlmodel.Field(foreign_key="categories.id", index=True)
    is_primary: bool = sqlmodel.Field(default=False, index=True)
    sort_order: int = sqlmodel.Field(default=0, index=True)

    contract: Contract = sqlmodel.Relationship(back_populates="category_links")
    category: Category = sqlmodel.Relationship(back_populates="contract_links")


class ContractRelation(TimestampedModel, table=True):
    """Typed relationship between two contract records."""

    __tablename__ = "contract_relations"
    __table_args__ = (
        sa.UniqueConstraint(
            "source_contract_id",
            "target_contract_id",
            "relation_type",
            name="uq_contract_relations_source_target_type",
        ),
        sa.CheckConstraint(
            "source_contract_id != target_contract_id",
            name="ck_contract_relations_distinct_contracts",
        ),
    )

    source_contract_id: int = sqlmodel.Field(foreign_key="contracts.id", index=True)
    target_contract_id: int = sqlmodel.Field(foreign_key="contracts.id", index=True)
    relation_type: ContractRelationType = sqlmodel.Field(index=True)
    note: str | None = sqlmodel.Field(default=None, max_length=255)

    source_contract: Contract = sqlmodel.Relationship(
        back_populates="outgoing_relations",
        sa_relationship_kwargs={"foreign_keys": "[ContractRelation.source_contract_id]"},
    )
    target_contract: Contract = sqlmodel.Relationship(
        back_populates="incoming_relations",
        sa_relationship_kwargs={"foreign_keys": "[ContractRelation.target_contract_id]"},
    )


class Star(TimestampedModel, table=True):
    """One star bookmark per user and contract."""

    __tablename__ = "stars"
    __table_args__ = (sa.UniqueConstraint("user_id", "contract_id", name="uq_stars_user_contract"),)

    user_id: int = sqlmodel.Field(foreign_key="users.id", index=True)
    contract_id: int = sqlmodel.Field(foreign_key="contracts.id", index=True)

    user: User = sqlmodel.Relationship(back_populates="stars")
    contract: Contract = sqlmodel.Relationship(back_populates="stars")


class Rating(TimestampedModel, table=True):
    """One editable rating per user and contract."""

    __tablename__ = "ratings"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "contract_id", name="uq_ratings_user_contract"),
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_ratings_score_range"),
    )

    user_id: int = sqlmodel.Field(foreign_key="users.id", index=True)
    contract_id: int = sqlmodel.Field(foreign_key="contracts.id", index=True)
    score: int = sqlmodel.Field(index=True)
    note: str | None = sqlmodel.Field(default=None, max_length=500)

    user: User = sqlmodel.Relationship(back_populates="ratings")
    contract: Contract = sqlmodel.Relationship(back_populates="ratings")


class PlaygroundTarget(TimestampedModel, table=True):
    """Saved playground identifier for a developer."""

    __tablename__ = "playground_targets"
    __table_args__ = (
        sa.UniqueConstraint(
            "user_id",
            "playground_id",
            name="uq_playground_targets_user_playground_id",
        ),
    )

    user_id: int = sqlmodel.Field(foreign_key="users.id", index=True)
    label: str = sqlmodel.Field(max_length=100)
    playground_id: str = sqlmodel.Field(max_length=128, index=True)
    is_default: bool = sqlmodel.Field(default=False, index=True)
    last_used_at: datetime | None = sqlmodel.Field(default=None, index=True)

    user: User = sqlmodel.Relationship(back_populates="playground_targets")
    deployments: list["DeploymentHistory"] = sqlmodel.Relationship(
        back_populates="playground_target",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class DeploymentHistory(TimestampedModel, table=True):
    """Recorded playground deployment attempt."""

    __tablename__ = "deployment_history"

    user_id: int = sqlmodel.Field(foreign_key="users.id", index=True)
    contract_version_id: int = sqlmodel.Field(foreign_key="contract_versions.id", index=True)
    playground_target_id: int | None = sqlmodel.Field(
        default=None,
        foreign_key="playground_targets.id",
        index=True,
    )
    playground_id: str = sqlmodel.Field(max_length=128, index=True)
    status: DeploymentStatus = sqlmodel.Field(default=DeploymentStatus.PENDING, index=True)
    transport: DeploymentTransport | None = sqlmodel.Field(default=None, index=True)
    external_request_id: str | None = sqlmodel.Field(default=None, max_length=255, index=True)
    redirect_url: str | None = sqlmodel.Field(default=None, max_length=1024)
    request_payload: dict[str, Any] = sqlmodel.Field(
        default_factory=dict,
        sa_column=sa.Column(sa.JSON, nullable=False),
    )
    response_payload: dict[str, Any] | None = sqlmodel.Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    error_payload: dict[str, Any] | None = sqlmodel.Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )
    initiated_at: datetime = sqlmodel.Field(default_factory=utc_now, index=True)
    completed_at: datetime | None = sqlmodel.Field(default=None, index=True)

    user: User = sqlmodel.Relationship(back_populates="deployments")
    contract_version: ContractVersion = sqlmodel.Relationship(back_populates="deployments")
    playground_target: Optional[PlaygroundTarget] = sqlmodel.Relationship(
        back_populates="deployments"
    )


class AdminAuditLog(TimestampedModel, table=True):
    """Immutable admin action record."""

    __tablename__ = "admin_audit_logs"

    admin_user_id: int = sqlmodel.Field(foreign_key="users.id", index=True)
    action: str = sqlmodel.Field(max_length=64, index=True)
    entity_type: str = sqlmodel.Field(max_length=64, index=True)
    entity_id: int | None = sqlmodel.Field(default=None, index=True)
    summary: str | None = sqlmodel.Field(default=None, max_length=255)
    details: dict[str, Any] = sqlmodel.Field(
        default_factory=dict,
        sa_column=sa.Column(sa.JSON, nullable=False),
    )

    admin_user: User = sqlmodel.Relationship(back_populates="admin_actions")


__all__ = [
    "AdminAuditLog",
    "Category",
    "Contract",
    "ContractCategoryLink",
    "ContractNetwork",
    "ContractRelation",
    "ContractRelationType",
    "ContractVersion",
    "DeploymentHistory",
    "DeploymentStatus",
    "DeploymentTransport",
    "LintStatus",
    "PlaygroundTarget",
    "Profile",
    "PublicationStatus",
    "Rating",
    "Star",
    "User",
    "UserRole",
    "UserStatus",
]
