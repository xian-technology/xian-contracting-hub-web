"""add package release schema

Revision ID: 31b8d04af1d2
Revises: 4f6e1e8d4c2b
Create Date: 2026-06-12 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "31b8d04af1d2"
down_revision: Union[str, Sequence[str], None] = "4f6e1e8d4c2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "contract_packages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("display_name", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("short_summary", sqlmodel.sql.sqltypes.AutoString(length=280), nullable=False),
        sa.Column("long_description", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "STANDALONE",
                "PRODUCT",
                "STANDARD",
                "EXAMPLE",
                name="contractpackagekind",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PUBLISHED", "ARCHIVED", "DEPRECATED", name="publicationstatus"),
            nullable=False,
        ),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("author_label", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.Column("documentation_url", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column(
            "source_repository_url",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("latest_published_release_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["latest_published_release_id"],
            ["contract_package_releases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("contract_packages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_contract_packages_author_user_id"),
            ["author_user_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_packages_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_contract_packages_display_name"),
            ["display_name"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_contract_packages_kind"), ["kind"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_contract_packages_latest_published_release_id"),
            ["latest_published_release_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_contract_packages_slug"), ["slug"], unique=True)
        batch_op.create_index(batch_op.f("ix_contract_packages_status"), ["status"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_contract_packages_updated_at"), ["updated_at"], unique=False
        )

    op.create_table(
        "contract_package_releases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("semantic_version", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PUBLISHED", "ARCHIVED", "DEPRECATED", name="publicationstatus"),
            nullable=False,
        ),
        sa.Column(
            "source_repository_url",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
        sa.Column("source_commit", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=True),
        sa.Column("source_tag", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.Column("manifest_path", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column(
            "manifest_hash_sha256",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=True,
        ),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["contract_packages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "package_id",
            "semantic_version",
            name="uq_contract_package_releases_package_semantic_version",
        ),
    )
    with op.batch_alter_table("contract_package_releases", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_contract_package_releases_created_at"),
            ["created_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_releases_manifest_hash_sha256"),
            ["manifest_hash_sha256"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_releases_package_id"),
            ["package_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_releases_published_at"),
            ["published_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_releases_semantic_version"),
            ["semantic_version"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_releases_source_commit"),
            ["source_commit"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_releases_source_tag"),
            ["source_tag"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_releases_status"),
            ["status"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_releases_updated_at"),
            ["updated_at"],
            unique=False,
        )

    op.create_table(
        "contract_package_release_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("contract_version_id", sa.Integer(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("source_path", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column(
            "source_hash_sha256",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=True,
        ),
        sa.Column("deploy_order", sa.Integer(), nullable=False),
        sa.Column("default_chi", sa.Integer(), nullable=True),
        sa.Column("deploy_default", sa.Boolean(), nullable=False),
        sa.Column("manifest_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["contract_version_id"], ["contract_versions.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["contract_package_releases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_id",
            "contract_version_id",
            name="uq_package_release_artifacts_release_contract_version",
        ),
    )
    with op.batch_alter_table("contract_package_release_artifacts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_contract_package_release_artifacts_contract_version_id"),
            ["contract_version_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_release_artifacts_created_at"),
            ["created_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_release_artifacts_deploy_default"),
            ["deploy_default"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_release_artifacts_deploy_order"),
            ["deploy_order"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_release_artifacts_release_id"),
            ["release_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_release_artifacts_role"),
            ["role"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_release_artifacts_source_hash_sha256"),
            ["source_hash_sha256"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contract_package_release_artifacts_updated_at"),
            ["updated_at"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("contract_package_release_artifacts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contract_package_release_artifacts_updated_at"))
        batch_op.drop_index(batch_op.f("ix_contract_package_release_artifacts_source_hash_sha256"))
        batch_op.drop_index(batch_op.f("ix_contract_package_release_artifacts_role"))
        batch_op.drop_index(batch_op.f("ix_contract_package_release_artifacts_release_id"))
        batch_op.drop_index(batch_op.f("ix_contract_package_release_artifacts_deploy_order"))
        batch_op.drop_index(batch_op.f("ix_contract_package_release_artifacts_deploy_default"))
        batch_op.drop_index(batch_op.f("ix_contract_package_release_artifacts_created_at"))
        batch_op.drop_index(batch_op.f("ix_contract_package_release_artifacts_contract_version_id"))
    op.drop_table("contract_package_release_artifacts")

    with op.batch_alter_table("contract_package_releases", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contract_package_releases_updated_at"))
        batch_op.drop_index(batch_op.f("ix_contract_package_releases_status"))
        batch_op.drop_index(batch_op.f("ix_contract_package_releases_source_tag"))
        batch_op.drop_index(batch_op.f("ix_contract_package_releases_source_commit"))
        batch_op.drop_index(batch_op.f("ix_contract_package_releases_semantic_version"))
        batch_op.drop_index(batch_op.f("ix_contract_package_releases_published_at"))
        batch_op.drop_index(batch_op.f("ix_contract_package_releases_package_id"))
        batch_op.drop_index(batch_op.f("ix_contract_package_releases_manifest_hash_sha256"))
        batch_op.drop_index(batch_op.f("ix_contract_package_releases_created_at"))
    op.drop_table("contract_package_releases")

    with op.batch_alter_table("contract_packages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contract_packages_updated_at"))
        batch_op.drop_index(batch_op.f("ix_contract_packages_status"))
        batch_op.drop_index(batch_op.f("ix_contract_packages_slug"))
        batch_op.drop_index(batch_op.f("ix_contract_packages_latest_published_release_id"))
        batch_op.drop_index(batch_op.f("ix_contract_packages_kind"))
        batch_op.drop_index(batch_op.f("ix_contract_packages_display_name"))
        batch_op.drop_index(batch_op.f("ix_contract_packages_created_at"))
        batch_op.drop_index(batch_op.f("ix_contract_packages_author_user_id"))
    op.drop_table("contract_packages")
