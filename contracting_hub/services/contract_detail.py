"""Service helpers for the public contract detail surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlmodel import Session

from contracting_hub.database import session_scope
from contracting_hub.models import (
    Contract,
    ContractNetwork,
    ContractRelation,
    ContractRelationType,
    ContractVersion,
    LintStatus,
    PublicationStatus,
)
from contracting_hub.repositories import ContractRepository, RatingRepository, StarRepository
from contracting_hub.services.contract_diffs import build_contract_version_diff
from contracting_hub.services.contract_metadata import validate_semantic_version


@dataclass(frozen=True)
class ContractDetailAuthorSummary:
    """Pure author summary rendered inside the public contract header."""

    display_name: str
    username: str | None
    bio: str | None
    website_url: str | None
    github_url: str | None
    xian_profile_url: str | None


@dataclass(frozen=True)
class ContractDetailVersionSummary:
    """Public version metadata rendered in the detail-page selector."""

    semantic_version: str
    status: PublicationStatus
    published_at: datetime | None
    changelog: str | None
    is_latest_public: bool


@dataclass(frozen=True)
class ContractDetailRelatedContractSummary:
    """Public summary of one visible related contract link."""

    slug: str
    display_name: str
    contract_name: str
    short_summary: str
    relation_type: ContractRelationType
    relation_label: str
    author_name: str
    primary_category_name: str | None
    latest_version_label: str


@dataclass(frozen=True)
class ContractDetailVersionDiffSummary:
    """Public diff metadata rendered for the selected contract version."""

    from_version: str | None
    to_version: str | None
    has_previous_version: bool
    has_changes: bool
    added_lines: int
    removed_lines: int
    line_delta: int
    from_line_count: int
    to_line_count: int
    hunk_count: int
    context_lines: int
    unified_diff: str | None


@dataclass(frozen=True)
class ContractDetailLintFinding:
    """Public lint finding metadata rendered for the selected contract version."""

    message: str
    severity: str
    line: int | None
    column: int | None


@dataclass(frozen=True)
class ContractDetailLintSummary:
    """Public lint summary rendered for the selected contract version."""

    status: LintStatus | None
    issue_count: int
    error_count: int
    warning_count: int
    info_count: int
    findings: tuple[ContractDetailLintFinding, ...]

    @property
    def has_report(self) -> bool:
        """Return whether the selected version carries lint metadata."""
        return self.status is not None or self.issue_count > 0 or bool(self.findings)


@dataclass(frozen=True)
class ContractDetailSnapshot:
    """Header-ready public contract detail data."""

    found: bool
    slug: str | None
    display_name: str
    contract_name: str
    short_summary: str
    long_description: str
    contract_status: PublicationStatus | None
    featured: bool
    network: ContractNetwork | None
    license_name: str | None
    documentation_url: str | None
    source_repository_url: str | None
    author: ContractDetailAuthorSummary
    primary_category_name: str | None
    category_names: tuple[str, ...]
    tag_names: tuple[str, ...]
    selected_version: str | None
    selected_version_status: PublicationStatus | None
    selected_version_source_code: str
    selected_version_changelog: str | None
    selected_version_published_at: datetime | None
    selected_version_is_latest_public: bool
    selected_version_lint: ContractDetailLintSummary
    selected_version_diff: ContractDetailVersionDiffSummary
    available_versions: tuple[ContractDetailVersionSummary, ...]
    outgoing_related_contracts: tuple[ContractDetailRelatedContractSummary, ...]
    incoming_related_contracts: tuple[ContractDetailRelatedContractSummary, ...]
    updated_at: datetime | None
    star_count: int
    rating_count: int
    average_rating: float | None


def normalize_contract_detail_slug(slug: str | None) -> str | None:
    """Normalize one public contract-detail slug from route params."""
    if slug is None:
        return None
    normalized = slug.strip().lower()
    return normalized or None


def build_empty_contract_detail_snapshot(*, slug: str | None = None) -> ContractDetailSnapshot:
    """Return a stable empty snapshot for loading failures or unknown slugs."""
    return ContractDetailSnapshot(
        found=False,
        slug=normalize_contract_detail_slug(slug),
        display_name="",
        contract_name="",
        short_summary="",
        long_description="",
        contract_status=None,
        featured=False,
        network=None,
        license_name=None,
        documentation_url=None,
        source_repository_url=None,
        author=ContractDetailAuthorSummary(
            display_name="Curated entry",
            username=None,
            bio=None,
            website_url=None,
            github_url=None,
            xian_profile_url=None,
        ),
        primary_category_name=None,
        category_names=(),
        tag_names=(),
        selected_version=None,
        selected_version_status=None,
        selected_version_source_code="",
        selected_version_changelog=None,
        selected_version_published_at=None,
        selected_version_is_latest_public=False,
        selected_version_lint=build_empty_contract_detail_lint_summary(),
        selected_version_diff=build_empty_contract_detail_version_diff_summary(),
        available_versions=(),
        outgoing_related_contracts=(),
        incoming_related_contracts=(),
        updated_at=None,
        star_count=0,
        rating_count=0,
        average_rating=None,
    )


def load_public_contract_detail_snapshot(
    *,
    session: Session,
    slug: str | None,
    semantic_version: str | None = None,
) -> ContractDetailSnapshot:
    """Load one published contract into a header-ready detail snapshot."""
    normalized_slug = normalize_contract_detail_slug(slug)
    if normalized_slug is None:
        return build_empty_contract_detail_snapshot()

    repository = ContractRepository(session)
    detail = repository.get_contract_detail(normalized_slug)
    if detail is None:
        return build_empty_contract_detail_snapshot(slug=normalized_slug)

    contract = detail.contract
    contract_id = contract.id
    if contract_id is None:
        return build_empty_contract_detail_snapshot(slug=normalized_slug)

    star_count = StarRepository(session).count_contract_stars(contract_id)
    rating_count, average_rating = RatingRepository(session).get_contract_rating_stats(contract_id)

    ordered_categories = _sorted_contract_category_links(contract)
    category_names = tuple(link.category.name for link in ordered_categories)
    primary_category_name = _build_primary_category_name(contract)
    latest_public_version = contract.latest_published_version or (
        detail.versions[0] if detail.versions else None
    )
    selected_version = _resolve_selected_version(
        versions=detail.versions,
        latest_public_version=latest_public_version,
        semantic_version=normalize_contract_detail_version(semantic_version),
    )
    selected_version_diff = _build_selected_version_diff(
        versions=detail.versions,
        selected_version=selected_version,
    )

    return ContractDetailSnapshot(
        found=True,
        slug=contract.slug,
        display_name=contract.display_name,
        contract_name=contract.contract_name,
        short_summary=contract.short_summary,
        long_description=contract.long_description,
        contract_status=contract.status,
        featured=contract.featured,
        network=contract.network,
        license_name=contract.license_name,
        documentation_url=contract.documentation_url,
        source_repository_url=contract.source_repository_url,
        author=_build_contract_detail_author(contract),
        primary_category_name=primary_category_name,
        category_names=category_names,
        tag_names=tuple(contract.tags),
        selected_version=(
            selected_version.semantic_version if selected_version is not None else None
        ),
        selected_version_status=selected_version.status if selected_version is not None else None,
        selected_version_source_code=selected_version.source_code if selected_version else "",
        selected_version_changelog=selected_version.changelog if selected_version else None,
        selected_version_published_at=_coerce_utc_datetime(
            selected_version.published_at if selected_version is not None else None
        ),
        selected_version_is_latest_public=_version_is_latest_public(
            version=selected_version,
            latest_public_version=latest_public_version,
        ),
        selected_version_lint=_build_contract_detail_lint_summary(selected_version),
        selected_version_diff=selected_version_diff,
        available_versions=tuple(
            _build_contract_detail_version_summary(
                version=version,
                latest_public_version=latest_public_version,
            )
            for version in detail.versions
        ),
        outgoing_related_contracts=_build_related_contract_summaries(
            detail.relations.outgoing,
            direction="outgoing",
        ),
        incoming_related_contracts=_build_related_contract_summaries(
            detail.relations.incoming,
            direction="incoming",
        ),
        updated_at=_coerce_utc_datetime(contract.updated_at),
        star_count=star_count,
        rating_count=rating_count,
        average_rating=average_rating,
    )


def load_public_contract_detail_snapshot_safe(
    *,
    slug: str | None,
    semantic_version: str | None = None,
) -> ContractDetailSnapshot:
    """Load one public contract detail while tolerating an unmigrated database."""
    normalized_slug = normalize_contract_detail_slug(slug)
    try:
        with session_scope() as session:
            return load_public_contract_detail_snapshot(
                session=session,
                slug=normalized_slug,
                semantic_version=semantic_version,
            )
    except (sa.exc.OperationalError, sa.exc.ProgrammingError):
        return build_empty_contract_detail_snapshot(slug=normalized_slug)


def _build_contract_detail_author(contract) -> ContractDetailAuthorSummary:
    profile = contract.author.profile if contract.author is not None else None
    display_name = contract.author_label or "Curated entry"
    username = None
    bio = None
    website_url = None
    github_url = None
    xian_profile_url = None

    if profile is not None:
        username = profile.username
        display_name = profile.display_name or profile.username
        bio = profile.bio
        website_url = profile.website_url
        github_url = profile.github_url
        xian_profile_url = profile.xian_profile_url

    return ContractDetailAuthorSummary(
        display_name=display_name,
        username=username,
        bio=bio,
        website_url=website_url,
        github_url=github_url,
        xian_profile_url=xian_profile_url,
    )


def _sorted_contract_category_links(contract: Contract):
    return tuple(
        sorted(
            contract.category_links,
            key=lambda link: (
                link.sort_order,
                link.category.sort_order,
                link.category.name.lower(),
                link.category.slug,
            ),
        )
    )


def _build_primary_category_name(contract: Contract) -> str | None:
    ordered_categories = _sorted_contract_category_links(contract)
    category_names = tuple(link.category.name for link in ordered_categories)
    return next(
        (link.category.name for link in ordered_categories if link.is_primary),
        category_names[0] if category_names else None,
    )


def _build_related_contract_summaries(
    relations: tuple[ContractRelation, ...],
    *,
    direction: str,
) -> tuple[ContractDetailRelatedContractSummary, ...]:
    if direction == "outgoing":
        return tuple(
            _build_related_contract_summary(
                related_contract=relation.target_contract,
                relation_type=relation.relation_type,
            )
            for relation in relations
        )
    if direction == "incoming":
        return tuple(
            _build_related_contract_summary(
                related_contract=relation.source_contract,
                relation_type=relation.relation_type,
            )
            for relation in relations
        )
    raise ValueError(f"Unsupported relation direction: {direction}")


def _build_related_contract_summary(
    *,
    related_contract: Contract,
    relation_type: ContractRelationType,
) -> ContractDetailRelatedContractSummary:
    author = _build_contract_detail_author(related_contract)
    latest_version = related_contract.latest_published_version

    return ContractDetailRelatedContractSummary(
        slug=related_contract.slug,
        display_name=related_contract.display_name,
        contract_name=related_contract.contract_name,
        short_summary=related_contract.short_summary,
        relation_type=relation_type,
        relation_label=_format_relation_type_label(relation_type),
        author_name=author.display_name,
        primary_category_name=_build_primary_category_name(related_contract),
        latest_version_label=(
            f"Latest {latest_version.semantic_version}"
            if latest_version is not None
            else "No public version"
        ),
    )


def normalize_contract_detail_version(semantic_version: str | None) -> str | None:
    """Normalize a requested public version without surfacing validation errors."""
    if semantic_version is None:
        return None
    try:
        return validate_semantic_version(semantic_version)
    except ValueError:
        return None


def build_empty_contract_detail_version_diff_summary(
    *,
    to_version: str | None = None,
    context_lines: int = 3,
) -> ContractDetailVersionDiffSummary:
    """Return a stable empty diff payload for versions without a public baseline."""
    return ContractDetailVersionDiffSummary(
        from_version=None,
        to_version=to_version,
        has_previous_version=False,
        has_changes=False,
        added_lines=0,
        removed_lines=0,
        line_delta=0,
        from_line_count=0,
        to_line_count=0,
        hunk_count=0,
        context_lines=context_lines,
        unified_diff=None,
    )


def build_empty_contract_detail_lint_summary() -> ContractDetailLintSummary:
    """Return a stable empty lint payload for versions without lint metadata."""
    return ContractDetailLintSummary(
        status=None,
        issue_count=0,
        error_count=0,
        warning_count=0,
        info_count=0,
        findings=(),
    )


def _resolve_selected_version(
    *,
    versions: tuple[ContractVersion, ...],
    latest_public_version: ContractVersion | None,
    semantic_version: str | None,
) -> ContractVersion | None:
    if semantic_version is not None:
        for version in versions:
            if version.semantic_version == semantic_version:
                return version

    if latest_public_version is not None:
        return latest_public_version
    return versions[0] if versions else None


def _build_selected_version_diff(
    *,
    versions: tuple[ContractVersion, ...],
    selected_version: ContractVersion | None,
) -> ContractDetailVersionDiffSummary:
    if selected_version is None:
        return build_empty_contract_detail_version_diff_summary()

    previous_visible_version = _resolve_previous_visible_version(
        versions=versions,
        selected_version=selected_version,
    )
    generated_diff = build_contract_version_diff(
        previous_source_code=(
            previous_visible_version.source_code if previous_visible_version is not None else None
        ),
        current_source_code=selected_version.source_code,
        from_version=(
            previous_visible_version.semantic_version
            if previous_visible_version is not None
            else None
        ),
        to_version=selected_version.semantic_version,
    )
    summary = generated_diff.summary
    return ContractDetailVersionDiffSummary(
        from_version=summary.get("from_version"),
        to_version=summary.get("to_version"),
        has_previous_version=bool(summary.get("has_previous_version")),
        has_changes=bool(summary.get("has_changes")),
        added_lines=int(summary.get("added_lines", 0)),
        removed_lines=int(summary.get("removed_lines", 0)),
        line_delta=int(summary.get("line_delta", 0)),
        from_line_count=int(summary.get("from_line_count", 0)),
        to_line_count=int(summary.get("to_line_count", 0)),
        hunk_count=int(summary.get("hunk_count", 0)),
        context_lines=int(summary.get("context_lines", 3)),
        unified_diff=generated_diff.unified_diff,
    )


def _build_contract_detail_lint_summary(
    version: ContractVersion | None,
) -> ContractDetailLintSummary:
    if version is None:
        return build_empty_contract_detail_lint_summary()

    findings = _normalize_lint_findings(version.lint_results)
    error_count, warning_count, info_count = _count_lint_findings(findings)
    summary = version.lint_summary or {}

    issue_count = _coerce_lint_count(summary.get("issue_count"), fallback=len(findings))
    return ContractDetailLintSummary(
        status=_normalize_lint_status(version.lint_status or summary.get("status")),
        issue_count=issue_count,
        error_count=_coerce_lint_count(summary.get("error_count"), fallback=error_count),
        warning_count=_coerce_lint_count(summary.get("warning_count"), fallback=warning_count),
        info_count=_coerce_lint_count(summary.get("info_count"), fallback=info_count),
        findings=findings,
    )


def _build_contract_detail_version_summary(
    *,
    version: ContractVersion,
    latest_public_version: ContractVersion | None,
) -> ContractDetailVersionSummary:
    return ContractDetailVersionSummary(
        semantic_version=version.semantic_version,
        status=version.status,
        published_at=_coerce_utc_datetime(version.published_at),
        changelog=version.changelog,
        is_latest_public=_version_is_latest_public(
            version=version,
            latest_public_version=latest_public_version,
        ),
    )


def _resolve_previous_visible_version(
    *,
    versions: tuple[ContractVersion, ...],
    selected_version: ContractVersion,
) -> ContractVersion | None:
    for index, version in enumerate(versions):
        if _versions_match(version, selected_version):
            next_index = index + 1
            return versions[next_index] if next_index < len(versions) else None

    previous_version = selected_version.previous_version
    while previous_version is not None and previous_version.status not in {
        PublicationStatus.PUBLISHED,
        PublicationStatus.DEPRECATED,
    }:
        previous_version = previous_version.previous_version
    return previous_version


def _version_is_latest_public(
    *,
    version: ContractVersion | None,
    latest_public_version: ContractVersion | None,
) -> bool:
    if version is None or latest_public_version is None:
        return False

    if version.id is not None and latest_public_version.id is not None:
        return version.id == latest_public_version.id
    return version.semantic_version == latest_public_version.semantic_version


def _versions_match(left: ContractVersion, right: ContractVersion) -> bool:
    if left.id is not None and right.id is not None:
        return left.id == right.id
    return left.semantic_version == right.semantic_version


def _coerce_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_lint_findings(
    raw_findings: list[dict[str, object]] | None,
) -> tuple[ContractDetailLintFinding, ...]:
    if not raw_findings:
        return ()

    findings: list[ContractDetailLintFinding] = []
    for raw_finding in raw_findings:
        if not isinstance(raw_finding, dict):
            continue
        position = raw_finding.get("position")
        line: int | None = None
        column: int | None = None
        if isinstance(position, dict):
            line = _coerce_optional_lint_count(position.get("line"))
            column = _coerce_optional_lint_count(position.get("column"))
        findings.append(
            ContractDetailLintFinding(
                message=str(raw_finding.get("message") or ""),
                severity=str(raw_finding.get("severity") or "info").lower().strip(),
                line=line,
                column=column,
            )
        )
    return tuple(findings)


def _count_lint_findings(
    findings: tuple[ContractDetailLintFinding, ...],
) -> tuple[int, int, int]:
    error_count = 0
    warning_count = 0
    info_count = 0

    for finding in findings:
        if finding.severity in {"error", "fatal"}:
            error_count += 1
        elif finding.severity in {"warn", "warning"}:
            warning_count += 1
        else:
            info_count += 1

    return error_count, warning_count, info_count


def _normalize_lint_status(value: object) -> LintStatus | None:
    if isinstance(value, LintStatus):
        return value
    if isinstance(value, str):
        normalized = value.lower().strip()
        try:
            return LintStatus(normalized)
        except ValueError:
            return None
    return None


def _coerce_lint_count(value: object, *, fallback: int) -> int:
    coerced = _coerce_optional_lint_count(value)
    if coerced is None:
        return fallback
    return coerced


def _coerce_optional_lint_count(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_relation_type_label(relation_type: ContractRelationType) -> str:
    labels = {
        ContractRelationType.DEPENDS_ON: "Depends on",
        ContractRelationType.COMPANION: "Companion",
        ContractRelationType.EXAMPLE_FOR: "Example for",
        ContractRelationType.EXTENDS: "Extends",
        ContractRelationType.SUPERSEDES: "Supersedes",
    }
    return labels[relation_type]


__all__ = [
    "ContractDetailAuthorSummary",
    "ContractDetailLintFinding",
    "ContractDetailLintSummary",
    "ContractDetailRelatedContractSummary",
    "ContractDetailSnapshot",
    "ContractDetailVersionDiffSummary",
    "ContractDetailVersionSummary",
    "build_empty_contract_detail_snapshot",
    "build_empty_contract_detail_lint_summary",
    "build_empty_contract_detail_version_diff_summary",
    "load_public_contract_detail_snapshot",
    "load_public_contract_detail_snapshot_safe",
    "normalize_contract_detail_slug",
    "normalize_contract_detail_version",
]
