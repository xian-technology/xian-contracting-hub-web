"""Public contract-detail page state."""

from __future__ import annotations

import re
from typing import TypedDict
from urllib.parse import quote

import reflex as rx

from contracting_hub.models import LintStatus, PublicationStatus
from contracting_hub.services import (
    ContractDetailSnapshot,
    load_public_contract_detail_snapshot_safe,
)
from contracting_hub.utils import build_contract_rating_display, format_contract_calendar_date
from contracting_hub.utils.meta import BROWSE_ROUTE, build_contract_detail_path


class AuthorLinkPayload(TypedDict):
    """Serialized public author link content stored in state."""

    label: str
    href: str


class VersionHistoryPayload(TypedDict):
    """Serialized public version metadata stored in state."""

    semantic_version: str
    href: str
    status_label: str
    status_color_scheme: str
    published_label: str
    is_selected: bool
    is_latest_public: bool


class LintFindingPayload(TypedDict):
    """Serialized selected-version lint issue stored in state."""

    severity_label: str
    severity_color_scheme: str
    message: str
    location_label: str


class ContractDetailState(rx.State):
    """Route-driven state for the public contract detail header."""

    load_state: str = "loading"
    contract_slug: str = ""
    display_name: str = ""
    contract_name: str = ""
    short_summary: str = ""
    long_description: str = ""
    header_context_label: str = ""
    contract_status_label: str = ""
    contract_status_color_scheme: str = "gray"
    version_label: str = ""
    version_status_label: str = ""
    version_status_color_scheme: str = "gray"
    selected_version_source_code: str = ""
    selected_version_changelog: str = ""
    selected_version_is_latest_public: bool = False
    selected_version_has_lint_report: bool = False
    selected_version_lint_status_label: str = "Unavailable"
    selected_version_lint_status_color_scheme: str = "gray"
    selected_version_lint_issue_count: int = 0
    selected_version_lint_error_count: int = 0
    selected_version_lint_warning_count: int = 0
    selected_version_lint_info_count: int = 0
    selected_version_lint_findings: list[LintFindingPayload] = []
    selected_version_diff_previous_version: str = ""
    selected_version_diff_unified_text: str = ""
    selected_version_diff_has_previous_version: bool = False
    selected_version_diff_has_changes: bool = False
    selected_version_diff_added_lines: int = 0
    selected_version_diff_removed_lines: int = 0
    selected_version_diff_line_delta: int = 0
    selected_version_diff_hunk_count: int = 0
    selected_version_diff_context_lines: int = 3
    available_versions: list[VersionHistoryPayload] = []
    version_count_label: str = "0 public versions"
    published_label: str = "Pending"
    updated_label: str = "Pending"
    star_count: str = "0"
    rating_headline: str = "No ratings yet"
    rating_detail: str = ""
    rating_empty: bool = True
    author_name: str = "Curated entry"
    author_secondary: str = ""
    author_initials: str = "CE"
    author_bio: str = ""
    author_links: list[AuthorLinkPayload] = []
    primary_category_label: str = "Uncategorized"
    category_labels: list[str] = []
    tag_labels: list[str] = []
    featured: bool = False
    network_label: str = ""
    license_label: str = ""
    documentation_url: str = ""
    source_repository_url: str = ""
    browse_href: str = BROWSE_ROUTE

    @rx.var
    def is_loading(self) -> bool:
        """Return whether the current route is loading detail data."""
        return self.load_state == "loading"

    @rx.var
    def is_ready(self) -> bool:
        """Return whether the current route resolved a visible contract."""
        return self.load_state == "ready"

    @rx.var
    def is_missing(self) -> bool:
        """Return whether the current route resolved to no visible contract."""
        return self.load_state == "missing"

    @rx.var
    def has_author_secondary(self) -> bool:
        """Return whether the author panel has a secondary identity line."""
        return bool(self.author_secondary)

    @rx.var
    def has_author_bio(self) -> bool:
        """Return whether the author panel has public bio copy."""
        return bool(self.author_bio)

    @rx.var
    def has_author_links(self) -> bool:
        """Return whether the author panel has outbound links."""
        return bool(self.author_links)

    @rx.var
    def has_tags(self) -> bool:
        """Return whether the current contract has public tags."""
        return bool(self.tag_labels)

    @rx.var
    def has_network(self) -> bool:
        """Return whether the contract has a network badge."""
        return bool(self.network_label)

    @rx.var
    def has_license(self) -> bool:
        """Return whether the contract has a license badge."""
        return bool(self.license_label)

    @rx.var
    def has_documentation_url(self) -> bool:
        """Return whether the contract has public documentation metadata."""
        return bool(self.documentation_url)

    @rx.var
    def has_source_repository_url(self) -> bool:
        """Return whether the contract has a public source repository URL."""
        return bool(self.source_repository_url)

    @rx.var
    def has_source_code(self) -> bool:
        """Return whether the selected version exposes source code."""
        return bool(self.selected_version_source_code)

    @rx.var
    def has_selected_version_changelog(self) -> bool:
        """Return whether the selected public version exposes release notes."""
        return bool(self.selected_version_changelog)

    @rx.var
    def has_selected_version_lint_findings(self) -> bool:
        """Return whether the selected public version exposes lint findings."""
        return bool(self.selected_version_lint_findings)

    @rx.var
    def has_selected_version_diff_content(self) -> bool:
        """Return whether the selected version exposes diff content to render."""
        return (
            self.selected_version_diff_has_previous_version
            and self.selected_version_diff_has_changes
            and bool(self.selected_version_diff_unified_text.strip())
        )

    @rx.var
    def selected_version_lint_issue_count_label(self) -> str:
        """Return one human-readable issue-count label."""
        return _format_lint_issue_count_label(self.selected_version_lint_issue_count)

    @rx.var
    def selected_version_lint_error_count_label(self) -> str:
        """Return one human-readable error-count label."""
        return _format_lint_error_count_label(self.selected_version_lint_error_count)

    @rx.var
    def selected_version_lint_warning_count_label(self) -> str:
        """Return one human-readable warning-count label."""
        return _format_lint_warning_count_label(self.selected_version_lint_warning_count)

    @rx.var
    def selected_version_lint_info_count_label(self) -> str:
        """Return one human-readable info-count label."""
        return _format_lint_info_count_label(self.selected_version_lint_info_count)

    @rx.var
    def selected_version_lint_summary_copy(self) -> str:
        """Return the detail copy shown in the lint panel header."""
        return _build_lint_summary_copy(
            has_report=self.selected_version_has_lint_report,
            issue_count=self.selected_version_lint_issue_count,
            status_label=self.selected_version_lint_status_label,
        )

    @rx.var
    def source_line_count_label(self) -> str:
        """Return a human-readable source-code line count."""
        return _format_line_count(_count_source_lines(self.selected_version_source_code))

    @rx.var
    def source_download_filename(self) -> str:
        """Return the filename used for source downloads."""
        return _build_source_download_filename(
            contract_name=self.contract_name,
            contract_slug=self.contract_slug,
            version_label=self.version_label,
        )

    @rx.var
    def source_download_url(self) -> str:
        """Return a data URL for the selected source snapshot."""
        return _build_source_download_url(self.selected_version_source_code)

    @rx.var
    def selected_version_diff_added_lines_label(self) -> str:
        """Return one human-readable added-lines label for the diff summary."""
        return _format_added_lines_label(self.selected_version_diff_added_lines)

    @rx.var
    def selected_version_diff_removed_lines_label(self) -> str:
        """Return one human-readable removed-lines label for the diff summary."""
        return _format_removed_lines_label(self.selected_version_diff_removed_lines)

    @rx.var
    def selected_version_diff_line_delta_label(self) -> str:
        """Return one human-readable net line-delta label."""
        return _format_line_delta_label(self.selected_version_diff_line_delta)

    @rx.var
    def selected_version_diff_hunk_count_label(self) -> str:
        """Return one human-readable hunk-count label."""
        return _format_hunk_count_label(self.selected_version_diff_hunk_count)

    @rx.var
    def selected_version_diff_context_lines_label(self) -> str:
        """Return one human-readable context-lines label."""
        return _format_context_lines_label(self.selected_version_diff_context_lines)

    def load_page(self) -> None:
        """Load one public contract snapshot from the current route params."""
        params = self.router.page.params
        snapshot = load_public_contract_detail_snapshot_safe(
            slug=params.get("slug"),
            semantic_version=params.get("version"),
        )
        self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot: ContractDetailSnapshot) -> None:
        if not snapshot.found:
            self._apply_missing(snapshot.slug)
            return

        rating_display = build_contract_rating_display(
            average_rating=snapshot.average_rating,
            rating_count=snapshot.rating_count,
        )
        self.load_state = "ready"
        self.contract_slug = snapshot.slug or ""
        self.display_name = snapshot.display_name
        self.contract_name = snapshot.contract_name
        self.short_summary = snapshot.short_summary
        self.long_description = snapshot.long_description
        self.version_label = snapshot.selected_version or "No published version"
        self.version_status_label = _status_label(snapshot.selected_version_status)
        self.version_status_color_scheme = _status_color_scheme(snapshot.selected_version_status)
        self.selected_version_source_code = snapshot.selected_version_source_code
        self.selected_version_changelog = snapshot.selected_version_changelog or ""
        self.selected_version_is_latest_public = snapshot.selected_version_is_latest_public
        self.selected_version_has_lint_report = snapshot.selected_version_lint.has_report
        self.selected_version_lint_status_label = _lint_status_label(
            snapshot.selected_version_lint.status
        )
        self.selected_version_lint_status_color_scheme = _lint_status_color_scheme(
            snapshot.selected_version_lint.status
        )
        self.selected_version_lint_issue_count = snapshot.selected_version_lint.issue_count
        self.selected_version_lint_error_count = snapshot.selected_version_lint.error_count
        self.selected_version_lint_warning_count = snapshot.selected_version_lint.warning_count
        self.selected_version_lint_info_count = snapshot.selected_version_lint.info_count
        self.selected_version_lint_findings = _serialize_lint_findings(snapshot)
        self.selected_version_diff_previous_version = (
            snapshot.selected_version_diff.from_version or ""
        )
        self.selected_version_diff_unified_text = snapshot.selected_version_diff.unified_diff or ""
        self.selected_version_diff_has_previous_version = (
            snapshot.selected_version_diff.has_previous_version
        )
        self.selected_version_diff_has_changes = snapshot.selected_version_diff.has_changes
        self.selected_version_diff_added_lines = snapshot.selected_version_diff.added_lines
        self.selected_version_diff_removed_lines = snapshot.selected_version_diff.removed_lines
        self.selected_version_diff_line_delta = snapshot.selected_version_diff.line_delta
        self.selected_version_diff_hunk_count = snapshot.selected_version_diff.hunk_count
        self.selected_version_diff_context_lines = snapshot.selected_version_diff.context_lines
        self.available_versions = _serialize_available_versions(snapshot)
        self.version_count_label = _format_version_count_label(len(snapshot.available_versions))
        self.published_label = format_contract_calendar_date(snapshot.selected_version_published_at)
        self.updated_label = format_contract_calendar_date(snapshot.updated_at)
        self.header_context_label = (
            f"Version {self.version_label} • Published {self.published_label} • "
            f"Updated {self.updated_label}"
        )
        self.contract_status_label = _status_label(snapshot.contract_status)
        self.contract_status_color_scheme = _status_color_scheme(snapshot.contract_status)
        self.star_count = str(snapshot.star_count)
        self.rating_headline = rating_display.headline
        self.rating_detail = rating_display.detail
        self.rating_empty = rating_display.empty
        self.author_name = snapshot.author.display_name
        self.author_secondary = (
            f"@{snapshot.author.username}" if snapshot.author.username else "Curated author"
        )
        self.author_initials = _author_initials(snapshot.author.display_name)
        self.author_bio = snapshot.author.bio or ""
        self.author_links = _serialize_author_links(snapshot)
        self.primary_category_label = snapshot.primary_category_name or "Uncategorized"
        self.category_labels = list(snapshot.category_names)
        self.tag_labels = list(snapshot.tag_names)
        self.featured = snapshot.featured
        self.network_label = (
            snapshot.network.value.replace("-", " ").title() if snapshot.network is not None else ""
        )
        self.license_label = snapshot.license_name or ""
        self.documentation_url = snapshot.documentation_url or ""
        self.source_repository_url = snapshot.source_repository_url or ""
        self.browse_href = BROWSE_ROUTE

    def _apply_missing(self, slug: str | None) -> None:
        self.load_state = "missing"
        self.contract_slug = slug or ""
        self.display_name = ""
        self.contract_name = ""
        self.short_summary = ""
        self.long_description = ""
        self.header_context_label = ""
        self.contract_status_label = ""
        self.contract_status_color_scheme = "gray"
        self.version_label = ""
        self.version_status_label = ""
        self.version_status_color_scheme = "gray"
        self.selected_version_source_code = ""
        self.selected_version_changelog = ""
        self.selected_version_is_latest_public = False
        self.selected_version_has_lint_report = False
        self.selected_version_lint_status_label = "Unavailable"
        self.selected_version_lint_status_color_scheme = "gray"
        self.selected_version_lint_issue_count = 0
        self.selected_version_lint_error_count = 0
        self.selected_version_lint_warning_count = 0
        self.selected_version_lint_info_count = 0
        self.selected_version_lint_findings = []
        self.selected_version_diff_previous_version = ""
        self.selected_version_diff_unified_text = ""
        self.selected_version_diff_has_previous_version = False
        self.selected_version_diff_has_changes = False
        self.selected_version_diff_added_lines = 0
        self.selected_version_diff_removed_lines = 0
        self.selected_version_diff_line_delta = 0
        self.selected_version_diff_hunk_count = 0
        self.selected_version_diff_context_lines = 3
        self.available_versions = []
        self.version_count_label = "0 public versions"
        self.published_label = "Pending"
        self.updated_label = "Pending"
        self.star_count = "0"
        self.rating_headline = "No ratings yet"
        self.rating_detail = ""
        self.rating_empty = True
        self.author_name = "Curated entry"
        self.author_secondary = ""
        self.author_initials = "CE"
        self.author_bio = ""
        self.author_links = []
        self.primary_category_label = "Uncategorized"
        self.category_labels = []
        self.tag_labels = []
        self.featured = False
        self.network_label = ""
        self.license_label = ""
        self.documentation_url = ""
        self.source_repository_url = ""
        self.browse_href = BROWSE_ROUTE


def _serialize_author_links(snapshot: ContractDetailSnapshot) -> list[AuthorLinkPayload]:
    links: list[AuthorLinkPayload] = []
    if snapshot.author.website_url:
        links.append({"label": "Website", "href": snapshot.author.website_url})
    if snapshot.author.github_url:
        links.append({"label": "GitHub", "href": snapshot.author.github_url})
    if snapshot.author.xian_profile_url:
        links.append({"label": "Xian", "href": snapshot.author.xian_profile_url})
    return links


def _serialize_available_versions(snapshot: ContractDetailSnapshot) -> list[VersionHistoryPayload]:
    if not snapshot.slug:
        return []

    return [
        {
            "semantic_version": version.semantic_version,
            "href": build_contract_detail_path(
                snapshot.slug,
                semantic_version=None if version.is_latest_public else version.semantic_version,
            ),
            "status_label": _status_label(version.status),
            "status_color_scheme": _status_color_scheme(version.status),
            "published_label": format_contract_calendar_date(version.published_at),
            "is_selected": version.semantic_version == snapshot.selected_version,
            "is_latest_public": version.is_latest_public,
        }
        for version in snapshot.available_versions
    ]


def _serialize_lint_findings(snapshot: ContractDetailSnapshot) -> list[LintFindingPayload]:
    return [
        {
            "severity_label": _format_lint_finding_severity(finding.severity),
            "severity_color_scheme": _lint_finding_color_scheme(finding.severity),
            "message": finding.message,
            "location_label": _format_lint_finding_location(finding.line, finding.column),
        }
        for finding in snapshot.selected_version_lint.findings
    ]


def _status_label(status: PublicationStatus | None) -> str:
    if status is None:
        return "Pending"
    return status.value.replace("_", " ").title()


def _status_color_scheme(status: PublicationStatus | None) -> str:
    if status is PublicationStatus.PUBLISHED:
        return "grass"
    if status in {PublicationStatus.DEPRECATED, PublicationStatus.ARCHIVED}:
        return "orange"
    if status is PublicationStatus.DRAFT:
        return "gray"
    return "gray"


def _author_initials(value: str) -> str:
    parts = [part[0].upper() for part in value.split() if part]
    if not parts:
        return "CE"
    return "".join(parts[:2])


def _count_source_lines(source_code: str) -> int:
    if not source_code:
        return 0
    return len(source_code.splitlines())


def _format_line_count(line_count: int) -> str:
    if line_count == 1:
        return "1 line"
    return f"{line_count} lines"


def _format_version_count_label(version_count: int) -> str:
    if version_count == 1:
        return "1 public version"
    return f"{version_count} public versions"


def _lint_status_label(status: LintStatus | None) -> str:
    if status is LintStatus.PASS:
        return "Pass"
    if status is LintStatus.WARN:
        return "Warn"
    if status is LintStatus.FAIL:
        return "Fail"
    return "Unavailable"


def _lint_status_color_scheme(status: LintStatus | None) -> str:
    if status is LintStatus.PASS:
        return "grass"
    if status is LintStatus.WARN:
        return "orange"
    if status is LintStatus.FAIL:
        return "tomato"
    return "gray"


def _format_lint_issue_count_label(issue_count: int) -> str:
    if issue_count == 1:
        return "1 issue"
    return f"{issue_count} issues"


def _format_lint_error_count_label(error_count: int) -> str:
    if error_count == 1:
        return "1 error"
    return f"{error_count} errors"


def _format_lint_warning_count_label(warning_count: int) -> str:
    if warning_count == 1:
        return "1 warning"
    return f"{warning_count} warnings"


def _format_lint_info_count_label(info_count: int) -> str:
    if info_count == 1:
        return "1 info note"
    return f"{info_count} info notes"


def _build_lint_summary_copy(
    *,
    has_report: bool,
    issue_count: int,
    status_label: str,
) -> str:
    if not has_report:
        return "Lint metadata is unavailable for this public release."
    if status_label == "Unavailable":
        return "Stored lint findings are available, but the summary status is unavailable."
    if issue_count == 0:
        return "No lint issues were reported for this public release."
    if status_label == "Fail":
        return "Blocking lint issues were detected and should be reviewed before reuse."
    if status_label == "Warn":
        return "Non-blocking lint warnings were detected for this public release."
    return "Review the lint findings captured for this public release."


def _format_added_lines_label(line_count: int) -> str:
    if line_count == 1:
        return "+1 line added"
    return f"+{line_count} lines added"


def _format_removed_lines_label(line_count: int) -> str:
    if line_count == 1:
        return "-1 line removed"
    return f"-{line_count} lines removed"


def _format_line_delta_label(line_delta: int) -> str:
    if line_delta == 0:
        return "No line delta"

    noun = "line" if abs(line_delta) == 1 else "lines"
    sign = "+" if line_delta > 0 else ""
    return f"{sign}{line_delta} {noun} net"


def _format_hunk_count_label(hunk_count: int) -> str:
    if hunk_count == 1:
        return "1 hunk"
    return f"{hunk_count} hunks"


def _format_context_lines_label(line_count: int) -> str:
    if line_count == 1:
        return "1 context line"
    return f"{line_count} context lines"


def _build_source_download_filename(
    *,
    contract_name: str,
    contract_slug: str,
    version_label: str,
) -> str:
    base_name = contract_name or contract_slug or "contract"
    normalized_base_name = _sanitize_filename_token(base_name)
    normalized_version_label = _sanitize_filename_token(version_label)
    if normalized_version_label:
        return f"{normalized_base_name}-{normalized_version_label}.py"
    return f"{normalized_base_name}.py"


def _sanitize_filename_token(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z._-]+", "_", value).strip("._-")
    return normalized or "contract"


def _build_source_download_url(source_code: str) -> str:
    if not source_code:
        return ""
    return f"data:text/x-python;charset=utf-8,{quote(source_code, safe='')}"


def _format_lint_finding_severity(severity: str) -> str:
    normalized = severity.lower().strip()
    if normalized in {"error", "fatal"}:
        return "Error"
    if normalized in {"warn", "warning"}:
        return "Warning"
    return "Info"


def _lint_finding_color_scheme(severity: str) -> str:
    normalized = severity.lower().strip()
    if normalized in {"error", "fatal"}:
        return "tomato"
    if normalized in {"warn", "warning"}:
        return "orange"
    return "gray"


def _format_lint_finding_location(line: int | None, column: int | None) -> str:
    if line is None or column is None or line <= 0 or column <= 0:
        return "General finding"
    return f"Line {line}, Column {column}"


__all__ = ["ContractDetailState"]
