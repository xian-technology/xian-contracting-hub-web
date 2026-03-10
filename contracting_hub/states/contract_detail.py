"""Public contract-detail page state."""

from __future__ import annotations

import re
from typing import Any, TypedDict
from urllib.parse import quote

import reflex as rx

from contracting_hub.config import get_settings
from contracting_hub.database import session_scope
from contracting_hub.models import (
    DeploymentStatus,
    DeploymentTransport,
    LintStatus,
    PublicationStatus,
    User,
)
from contracting_hub.services.auth import resolve_current_user
from contracting_hub.services.contract_detail import (
    ContractDetailSnapshot,
    load_contract_detail_engagement_snapshot_safe,
    load_public_contract_detail_snapshot_safe,
)
from contracting_hub.services.deployments import (
    ContractDeploymentAttemptResult,
    ContractDeploymentServiceError,
    deploy_contract_version,
)
from contracting_hub.services.playground_targets import list_playground_targets
from contracting_hub.services.ratings import ContractRatingServiceError, submit_contract_rating
from contracting_hub.services.stars import ContractStarServiceError, toggle_contract_star
from contracting_hub.states.auth import AUTH_SESSION_COOKIE_NAME, POST_LOGIN_PATH_STORAGE_KEY
from contracting_hub.utils import build_contract_rating_display, format_contract_calendar_date
from contracting_hub.utils.meta import (
    BROWSE_ROUTE,
    LOGIN_ROUTE,
    build_contract_detail_path,
    build_developer_profile_path,
)

_SETTINGS = get_settings()
DEPLOYMENT_TARGET_MODE_SAVED = "saved"
DEPLOYMENT_TARGET_MODE_AD_HOC = "ad_hoc"


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


class RelatedContractPayload(TypedDict):
    """Serialized related-contract entry stored in detail-page state."""

    relation_label: str
    href: str
    display_name: str
    contract_name: str
    short_summary: str
    author_label: str
    primary_category_label: str
    latest_version_label: str


class PlaygroundTargetOptionPayload(TypedDict):
    """Serialized saved playground target option for deployment selection."""

    id: int
    label: str
    playground_id: str
    option_label: str
    helper_label: str
    is_default: bool


class ContractDetailState(rx.State):
    """Route-driven state for the public contract detail header."""

    auth_session_token: str = rx.Cookie(
        "",
        name=AUTH_SESSION_COOKIE_NAME,
        path="/",
        same_site="lax",
        secure=_SETTINGS.environment == "production",
    )
    post_login_path: str = rx.LocalStorage("", name=POST_LOGIN_PATH_STORAGE_KEY)
    current_user_id: int | None = None
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
    outgoing_related_contracts: list[RelatedContractPayload] = []
    incoming_related_contracts: list[RelatedContractPayload] = []
    version_count_label: str = "0 public versions"
    related_contract_count_label: str = "0 public links"
    outgoing_related_contract_count_label: str = "0 outgoing links"
    incoming_related_contract_count_label: str = "0 incoming links"
    published_label: str = "Pending"
    updated_label: str = "Pending"
    star_count_value: int = 0
    star_count: str = "0"
    rating_count_value: int = 0
    average_rating_value: float | None = None
    rating_headline: str = "No ratings yet"
    rating_detail: str = ""
    rating_empty: bool = True
    starred_by_current_user: bool = False
    current_user_rating_score: int | None = None
    star_pending: bool = False
    rating_pending: bool = False
    engagement_success_message: str = ""
    engagement_error_message: str = ""
    engagement_login_prompt_message: str = ""
    deployment_drawer_open: bool = False
    deployment_pending: bool = False
    deployment_version: str = ""
    deployment_target_mode: str = DEPLOYMENT_TARGET_MODE_AD_HOC
    deployment_saved_target_id: str = ""
    deployment_ad_hoc_playground_id: str = ""
    deployment_saved_targets: list[PlaygroundTargetOptionPayload] = []
    deployment_target_count_label: str = "0 saved targets"
    deployment_form_error: str = ""
    deployment_version_error: str = ""
    deployment_saved_target_error: str = ""
    deployment_playground_id_error: str = ""
    deployment_result_status_label: str = ""
    deployment_result_status_color_scheme: str = "gray"
    deployment_result_message: str = ""
    deployment_result_detail: str = ""
    deployment_result_redirect_url: str = ""
    deployment_result_transport_label: str = ""
    deployment_result_external_request_id: str = ""
    author_name: str = "Curated entry"
    author_secondary: str = ""
    author_initials: str = "CE"
    author_bio: str = ""
    author_profile_href: str = ""
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
    def is_authenticated(self) -> bool:
        """Return whether the current browser has an active user session."""
        return self.current_user_id is not None

    @rx.var
    def current_detail_path(self) -> str:
        """Return the current detail route used for post-login redirects."""
        if not self.contract_slug:
            return BROWSE_ROUTE
        selected_version = None if self.selected_version_is_latest_public else self.version_label
        return build_contract_detail_path(
            self.contract_slug,
            semantic_version=selected_version,
        )

    @rx.var
    def has_current_user_rating(self) -> bool:
        """Return whether the current user has already rated this contract."""
        return self.current_user_rating_score is not None

    @rx.var
    def current_user_rating_label(self) -> str:
        """Return a compact personalized rating summary."""
        if self.current_user_rating_score is None:
            return "Choose a score from 1 to 5."
        return f"Your rating: {self.current_user_rating_score}/5"

    @rx.var
    def engagement_login_copy(self) -> str:
        """Return the anonymous engagement helper copy."""
        if self.engagement_login_prompt_message:
            return self.engagement_login_prompt_message
        return "Log in to save favorites and rate this contract."

    @rx.var
    def has_deployment_saved_targets(self) -> bool:
        """Return whether the authenticated user has saved deploy targets."""
        return bool(self.deployment_saved_targets)

    @rx.var
    def using_saved_deployment_target(self) -> bool:
        """Return whether the drawer is using a saved playground target."""
        return self.deployment_target_mode == DEPLOYMENT_TARGET_MODE_SAVED

    @rx.var
    def using_ad_hoc_deployment_target(self) -> bool:
        """Return whether the drawer is using an ad hoc playground ID."""
        return self.deployment_target_mode == DEPLOYMENT_TARGET_MODE_AD_HOC

    @rx.var
    def deployment_submit_label(self) -> str:
        """Return the deployment submit-button copy."""
        if self.deployment_pending:
            return "Submitting deployment..."
        return "Deploy version"

    @rx.var
    def has_deployment_result(self) -> bool:
        """Return whether the drawer has a recorded deployment result to render."""
        return bool(self.deployment_result_message)

    @rx.var
    def has_deployment_result_detail(self) -> bool:
        """Return whether the drawer has secondary result detail copy."""
        return bool(self.deployment_result_detail)

    @rx.var
    def has_deployment_result_redirect_url(self) -> bool:
        """Return whether the drawer can link to a generated playground redirect."""
        return bool(self.deployment_result_redirect_url)

    @rx.var
    def has_deployment_result_transport_label(self) -> bool:
        """Return whether the drawer should show the adapter transport label."""
        return bool(self.deployment_result_transport_label)

    @rx.var
    def has_deployment_result_external_request_id(self) -> bool:
        """Return whether the drawer should show an external request identifier."""
        return bool(self.deployment_result_external_request_id)

    @rx.var
    def star_button_label(self) -> str:
        """Return the inline star button label."""
        if self.star_pending:
            return "Updating favorite..."
        return "Starred" if self.starred_by_current_user else "Star contract"

    @rx.var
    def star_button_helper(self) -> str:
        """Return a personalized star-status line."""
        if not self.is_authenticated:
            return _format_total_stars_label(self.star_count_value)
        if self.starred_by_current_user:
            return "Saved in your favorites."
        return "Save this release to your favorites."

    @rx.var
    def star_total_label(self) -> str:
        """Return the current public star total."""
        return _format_total_stars_label(self.star_count_value)

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
    def has_author_profile_href(self) -> bool:
        """Return whether the author panel can deep-link to a public profile."""
        return bool(self.author_profile_href)

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
    def has_outgoing_related_contracts(self) -> bool:
        """Return whether the current contract exposes outgoing public links."""
        return bool(self.outgoing_related_contracts)

    @rx.var
    def has_incoming_related_contracts(self) -> bool:
        """Return whether public contracts point back to the current entry."""
        return bool(self.incoming_related_contracts)

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
        self._clear_engagement_feedback()
        self._clear_deployment_feedback(reset_result=True)
        self.star_pending = False
        self.rating_pending = False
        self._apply_user_snapshot(self._resolve_user_from_cookie())
        params = self.router.page.params
        snapshot = load_public_contract_detail_snapshot_safe(
            slug=params.get("slug"),
            semantic_version=params.get("version"),
        )
        self._apply_snapshot(snapshot)
        self._load_engagement_state()
        self._load_deployment_state()

    def begin_engagement_login(self) -> rx.event.EventSpec:
        """Remember the current detail route and redirect to the login screen."""
        self.post_login_path = self.current_detail_path
        return rx.redirect(LOGIN_ROUTE, replace=True)

    def begin_deployment_login(self) -> rx.event.EventSpec:
        """Remember the current detail route and redirect to login before deployment."""
        self.post_login_path = self.current_detail_path
        return rx.redirect(LOGIN_ROUTE, replace=True)

    def open_deployment_drawer(self):
        """Open the deployment drawer for the current authenticated user."""
        self._apply_user_snapshot(self._resolve_user_from_cookie())
        if self.current_user_id is None:
            return self.begin_deployment_login()
        self._load_deployment_targets()
        self._reset_deployment_form(reset_result=True)
        self.deployment_drawer_open = True
        yield
        return rx.set_focus("contract-deployment-version")

    def close_deployment_drawer(self) -> rx.event.EventSpec | None:
        """Close the deployment drawer when no submission is in progress."""
        if self.deployment_pending:
            return None
        self.deployment_drawer_open = False
        return rx.set_focus("contract-deployment-trigger")

    def set_deployment_version(self, value: str) -> None:
        """Update the selected deployment version."""
        self.deployment_version = value
        self.deployment_version_error = ""

    def set_deployment_target_mode(self, value: str) -> None:
        """Switch between saved-target and ad hoc deployment selection."""
        self.deployment_target_mode = _normalize_deployment_target_mode(
            value,
            has_saved_targets=bool(self.deployment_saved_targets),
        )
        if (
            self.deployment_target_mode == DEPLOYMENT_TARGET_MODE_SAVED
            and not self.deployment_saved_target_id
        ):
            self.deployment_saved_target_id = _default_saved_target_id(
                self.deployment_saved_targets
            )
        self.deployment_form_error = ""
        self.deployment_saved_target_error = ""
        self.deployment_playground_id_error = ""

    def set_deployment_saved_target_id(self, value: str) -> None:
        """Update the selected saved playground target."""
        self.deployment_saved_target_id = value
        self.deployment_saved_target_error = ""

    def set_deployment_ad_hoc_playground_id(self, value: str) -> None:
        """Update the ad hoc playground identifier input."""
        self.deployment_ad_hoc_playground_id = value
        self.deployment_playground_id_error = ""

    def submit_deployment(self, form_data: dict[str, Any]):
        """Submit the selected contract version to the configured playground."""
        self._clear_deployment_feedback(reset_result=True)
        self._apply_user_snapshot(self._resolve_user_from_cookie())
        user_id = self.current_user_id
        if user_id is None:
            self.deployment_form_error = "Log in to deploy this contract."
            self.deployment_drawer_open = False
            self.post_login_path = self.current_detail_path
            return
        if not self.contract_slug:
            self.deployment_form_error = "A contract must be loaded before deployment."
            return

        selected_version = str(form_data.get("semantic_version", self.deployment_version)).strip()
        self.deployment_version = selected_version
        selected_target_mode = _normalize_deployment_target_mode(
            str(form_data.get("target_mode", self.deployment_target_mode)),
            has_saved_targets=bool(self.deployment_saved_targets),
        )
        self.deployment_target_mode = selected_target_mode
        self.deployment_saved_target_id = str(
            form_data.get("playground_target_id", self.deployment_saved_target_id)
        ).strip()
        self.deployment_ad_hoc_playground_id = str(
            form_data.get("playground_id", self.deployment_ad_hoc_playground_id)
        )

        if not selected_version:
            self.deployment_version_error = "Choose a contract version to deploy."
            return

        selected_target_id: int | None = None
        ad_hoc_playground_id: str | None = None
        if selected_target_mode == DEPLOYMENT_TARGET_MODE_SAVED:
            if not self.deployment_saved_target_id:
                self.deployment_saved_target_error = "Choose one of your saved playground targets."
                return
            try:
                selected_target_id = int(self.deployment_saved_target_id)
            except ValueError:
                self.deployment_saved_target_error = "Choose one of your saved playground targets."
                return
        else:
            ad_hoc_playground_id = self.deployment_ad_hoc_playground_id

        self.deployment_pending = True
        yield

        try:
            with session_scope() as session:
                result = deploy_contract_version(
                    session=session,
                    user_id=user_id,
                    contract_slug=self.contract_slug,
                    semantic_version=selected_version,
                    playground_target_id=selected_target_id,
                    playground_id=ad_hoc_playground_id,
                    client_context={"request_origin": "contract_detail"},
                )
        except ContractDeploymentServiceError as error:
            self._apply_deployment_service_error(error)
            self.deployment_pending = False
            return
        except Exception:
            self.deployment_form_error = "The deployment request could not be completed."
            self.deployment_pending = False
            return

        self._load_deployment_targets()
        self._apply_deployment_result(result)
        self.deployment_pending = False

    def toggle_star(self):
        """Toggle the current user's star state with optimistic feedback."""
        user_id = self._prepare_engagement_action(
            prompt="Log in to star this contract.",
        )
        if user_id is None or not self.contract_slug:
            return

        previous_starred = self.starred_by_current_user
        previous_star_count = self.star_count_value
        self.star_pending = True
        self.starred_by_current_user = not previous_starred
        self._apply_star_count(
            previous_star_count + (1 if not previous_starred else -1),
        )
        yield

        try:
            with session_scope() as session:
                result = toggle_contract_star(
                    session=session,
                    user_id=user_id,
                    contract_slug=self.contract_slug,
                )
        except ContractStarServiceError as error:
            self.starred_by_current_user = previous_starred
            self._apply_star_count(previous_star_count)
            self.engagement_error_message = str(error)
            self.star_pending = False
            return
        except Exception:
            self.starred_by_current_user = previous_starred
            self._apply_star_count(previous_star_count)
            self.engagement_error_message = "The favorite action could not be completed."
            self.star_pending = False
            return

        self.starred_by_current_user = result.starred_by_user
        self._apply_star_count(result.star_count)
        self.engagement_success_message = (
            "Saved to favorites." if result.starred_by_user else "Removed from favorites."
        )
        self.star_pending = False

    def submit_rating(self, score: int):
        """Create or update the current user's rating with optimistic feedback."""
        user_id = self._prepare_engagement_action(
            prompt="Log in to rate this contract.",
        )
        if user_id is None or not self.contract_slug:
            return

        previous_rating_score = self.current_user_rating_score
        previous_rating_count = self.rating_count_value
        previous_average_rating = self.average_rating_value
        self.rating_pending = True
        self.current_user_rating_score = score
        optimistic_average, optimistic_count = _build_optimistic_rating_aggregate(
            average_rating=previous_average_rating,
            rating_count=previous_rating_count,
            previous_score=previous_rating_score,
            submitted_score=score,
        )
        self._apply_rating_aggregate(
            average_rating=optimistic_average,
            rating_count=optimistic_count,
        )
        yield

        try:
            with session_scope() as session:
                result = submit_contract_rating(
                    session=session,
                    user_id=user_id,
                    contract_slug=self.contract_slug,
                    score=score,
                )
        except ContractRatingServiceError as error:
            self.current_user_rating_score = previous_rating_score
            self._apply_rating_aggregate(
                average_rating=previous_average_rating,
                rating_count=previous_rating_count,
            )
            self.engagement_error_message = str(error)
            self.rating_pending = False
            return
        except Exception:
            self.current_user_rating_score = previous_rating_score
            self._apply_rating_aggregate(
                average_rating=previous_average_rating,
                rating_count=previous_rating_count,
            )
            self.engagement_error_message = "The rating could not be saved."
            self.rating_pending = False
            return

        self.current_user_rating_score = result.score
        self._apply_rating_aggregate(
            average_rating=result.average_score,
            rating_count=result.rating_count,
        )
        self.engagement_success_message = (
            "Rating updated." if result.updated_existing else "Rating saved."
        )
        self.rating_pending = False

    def _apply_snapshot(self, snapshot: ContractDetailSnapshot) -> None:
        if not snapshot.found:
            self._apply_missing(snapshot.slug)
            return
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
        self.outgoing_related_contracts = _serialize_related_contracts(
            snapshot.outgoing_related_contracts
        )
        self.incoming_related_contracts = _serialize_related_contracts(
            snapshot.incoming_related_contracts
        )
        self.version_count_label = _format_version_count_label(len(snapshot.available_versions))
        total_related_contracts = len(snapshot.outgoing_related_contracts) + len(
            snapshot.incoming_related_contracts
        )
        self.related_contract_count_label = _format_related_contract_count_label(
            total_related_contracts
        )
        self.outgoing_related_contract_count_label = _format_relation_group_count_label(
            len(snapshot.outgoing_related_contracts),
            direction="outgoing",
        )
        self.incoming_related_contract_count_label = _format_relation_group_count_label(
            len(snapshot.incoming_related_contracts),
            direction="incoming",
        )
        self.published_label = format_contract_calendar_date(snapshot.selected_version_published_at)
        self.updated_label = format_contract_calendar_date(snapshot.updated_at)
        self.header_context_label = (
            f"Version {self.version_label} • Published {self.published_label} • "
            f"Updated {self.updated_label}"
        )
        self.contract_status_label = _status_label(snapshot.contract_status)
        self.contract_status_color_scheme = _status_color_scheme(snapshot.contract_status)
        self._apply_star_count(snapshot.star_count)
        self._apply_rating_aggregate(
            average_rating=snapshot.average_rating,
            rating_count=snapshot.rating_count,
        )
        self.author_name = snapshot.author.display_name
        self.author_secondary = (
            f"@{snapshot.author.username}" if snapshot.author.username else "Curated author"
        )
        self.author_initials = _author_initials(snapshot.author.display_name)
        self.author_bio = snapshot.author.bio or ""
        self.author_profile_href = (
            build_developer_profile_path(snapshot.author.username)
            if snapshot.author.username
            else ""
        )
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
        self.outgoing_related_contracts = []
        self.incoming_related_contracts = []
        self.version_count_label = "0 public versions"
        self.related_contract_count_label = "0 public links"
        self.outgoing_related_contract_count_label = "0 outgoing links"
        self.incoming_related_contract_count_label = "0 incoming links"
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
        self.author_profile_href = ""
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
        self._reset_engagement_state()
        self._reset_deployment_state()

    def _load_engagement_state(self) -> None:
        self.starred_by_current_user = False
        self.current_user_rating_score = None
        if self.current_user_id is None or not self.contract_slug or not self.is_ready:
            return

        snapshot = load_contract_detail_engagement_snapshot_safe(
            user_id=self.current_user_id,
            slug=self.contract_slug,
        )
        self.starred_by_current_user = snapshot.starred_by_user
        self.current_user_rating_score = snapshot.current_user_rating_score

    def _load_deployment_state(self) -> None:
        self.deployment_drawer_open = False
        self.deployment_pending = False
        self._clear_deployment_feedback(reset_result=True)
        self.deployment_version = _resolve_deployment_version(
            selected_version=self.version_label,
            available_versions=self.available_versions,
        )
        self.deployment_ad_hoc_playground_id = ""
        if self.current_user_id is None or not self.contract_slug or not self.is_ready:
            self.deployment_saved_targets = []
            self.deployment_target_count_label = "0 saved targets"
            self.deployment_target_mode = DEPLOYMENT_TARGET_MODE_AD_HOC
            self.deployment_saved_target_id = ""
            return

        self._load_deployment_targets()
        self._reset_deployment_form(reset_result=True)

    def _load_deployment_targets(self) -> None:
        user_id = self.current_user_id
        if user_id is None:
            self.deployment_saved_targets = []
            self.deployment_target_count_label = "0 saved targets"
            self.deployment_target_mode = DEPLOYMENT_TARGET_MODE_AD_HOC
            self.deployment_saved_target_id = ""
            return

        try:
            with session_scope() as session:
                targets = list_playground_targets(session=session, user_id=user_id)
        except Exception:
            self.deployment_saved_targets = []
            self.deployment_target_count_label = "0 saved targets"
            self.deployment_target_mode = DEPLOYMENT_TARGET_MODE_AD_HOC
            self.deployment_saved_target_id = ""
            return
        self._apply_deployment_targets(targets)

    def _apply_deployment_targets(self, targets) -> None:
        serialized_targets = _serialize_playground_target_options(targets)
        self.deployment_saved_targets = serialized_targets
        self.deployment_target_count_label = _format_saved_target_count_label(
            len(serialized_targets)
        )
        if not serialized_targets:
            self.deployment_saved_target_id = ""
            self.deployment_target_mode = DEPLOYMENT_TARGET_MODE_AD_HOC
            return

        if not _saved_target_id_exists(
            saved_target_id=self.deployment_saved_target_id,
            targets=serialized_targets,
        ):
            self.deployment_saved_target_id = _default_saved_target_id(serialized_targets)

    def _reset_deployment_form(self, *, reset_result: bool) -> None:
        self.deployment_version = _resolve_deployment_version(
            selected_version=self.version_label,
            available_versions=self.available_versions,
        )
        self.deployment_saved_target_id = _default_saved_target_id(self.deployment_saved_targets)
        self.deployment_target_mode = (
            DEPLOYMENT_TARGET_MODE_SAVED
            if self.deployment_saved_target_id
            else DEPLOYMENT_TARGET_MODE_AD_HOC
        )
        self.deployment_ad_hoc_playground_id = ""
        self._clear_deployment_feedback(reset_result=reset_result)

    def _apply_deployment_service_error(self, error: ContractDeploymentServiceError) -> None:
        field_messages = {
            "semantic_version": "Choose a visible contract version to deploy.",
            "playground_target_id": "Choose one of your saved playground targets.",
            "playground_id": "Enter a playground ID to continue.",
        }
        message = field_messages.get(error.field, str(error))
        if error.field == "semantic_version":
            self.deployment_version_error = message
            return
        if error.field == "playground_target_id":
            self.deployment_saved_target_error = message
            return
        if error.field == "playground_id":
            self.deployment_playground_id_error = message
            return
        self.deployment_form_error = str(error)

    def _apply_deployment_result(
        self,
        result: ContractDeploymentAttemptResult,
    ) -> None:
        self.deployment_result_status_label = _deployment_status_label(result.status)
        self.deployment_result_status_color_scheme = _deployment_status_color_scheme(result.status)
        self.deployment_result_message = _build_deployment_result_message(result)
        self.deployment_result_detail = _build_deployment_result_detail(result)
        self.deployment_result_redirect_url = result.redirect_url or ""
        self.deployment_result_transport_label = _format_deployment_transport_label(
            result.transport
        )
        self.deployment_result_external_request_id = result.external_request_id or ""

    def _prepare_engagement_action(self, *, prompt: str) -> int | None:
        self._clear_engagement_feedback()
        self._apply_user_snapshot(self._resolve_user_from_cookie())
        if self.current_user_id is None:
            self.post_login_path = self.current_detail_path
            self.engagement_login_prompt_message = prompt
            return None
        return self.current_user_id

    def _apply_star_count(self, star_count: int) -> None:
        safe_star_count = max(star_count, 0)
        self.star_count_value = safe_star_count
        self.star_count = str(safe_star_count)

    def _apply_rating_aggregate(
        self,
        *,
        average_rating: float | None,
        rating_count: int,
    ) -> None:
        rating_display = build_contract_rating_display(
            average_rating=average_rating,
            rating_count=rating_count,
        )
        self.average_rating_value = average_rating
        self.rating_count_value = max(rating_count, 0)
        self.rating_headline = rating_display.headline
        self.rating_detail = rating_display.detail
        self.rating_empty = rating_display.empty

    def _clear_engagement_feedback(self) -> None:
        self.engagement_success_message = ""
        self.engagement_error_message = ""
        self.engagement_login_prompt_message = ""

    def _clear_deployment_feedback(self, *, reset_result: bool) -> None:
        self.deployment_form_error = ""
        self.deployment_version_error = ""
        self.deployment_saved_target_error = ""
        self.deployment_playground_id_error = ""
        if not reset_result:
            return
        self.deployment_result_status_label = ""
        self.deployment_result_status_color_scheme = "gray"
        self.deployment_result_message = ""
        self.deployment_result_detail = ""
        self.deployment_result_redirect_url = ""
        self.deployment_result_transport_label = ""
        self.deployment_result_external_request_id = ""

    def _reset_engagement_state(self) -> None:
        self._clear_engagement_feedback()
        self._apply_star_count(0)
        self._apply_rating_aggregate(
            average_rating=None,
            rating_count=0,
        )
        self.starred_by_current_user = False
        self.current_user_rating_score = None
        self.star_pending = False
        self.rating_pending = False

    def _reset_deployment_state(self) -> None:
        self.deployment_drawer_open = False
        self.deployment_pending = False
        self.deployment_version = ""
        self.deployment_target_mode = DEPLOYMENT_TARGET_MODE_AD_HOC
        self.deployment_saved_target_id = ""
        self.deployment_ad_hoc_playground_id = ""
        self.deployment_saved_targets = []
        self.deployment_target_count_label = "0 saved targets"
        self._clear_deployment_feedback(reset_result=True)

    def _resolve_user_from_cookie(self) -> User | None:
        with session_scope() as session:
            return resolve_current_user(
                session=session,
                session_token=self.auth_session_token,
            )

    def _apply_user_snapshot(self, user: User | None) -> None:
        if user is None:
            if self.auth_session_token:
                self.auth_session_token = ""
            self.current_user_id = None
            return

        self.current_user_id = user.id


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


def _serialize_related_contracts(
    relations,
) -> list[RelatedContractPayload]:
    return [
        {
            "relation_label": relation.relation_label,
            "href": build_contract_detail_path(relation.slug),
            "display_name": relation.display_name,
            "contract_name": relation.contract_name,
            "short_summary": relation.short_summary,
            "author_label": relation.author_name,
            "primary_category_label": relation.primary_category_name or "Uncategorized",
            "latest_version_label": relation.latest_version_label,
        }
        for relation in relations
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


def _format_related_contract_count_label(relation_count: int) -> str:
    if relation_count == 1:
        return "1 public link"
    return f"{relation_count} public links"


def _format_relation_group_count_label(relation_count: int, *, direction: str) -> str:
    noun = "link" if relation_count == 1 else "links"
    return f"{relation_count} {direction} {noun}"


def _format_total_stars_label(star_count: int) -> str:
    if star_count == 1:
        return "1 total star"
    return f"{star_count} total stars"


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


def _build_optimistic_rating_aggregate(
    *,
    average_rating: float | None,
    rating_count: int,
    previous_score: int | None,
    submitted_score: int,
) -> tuple[float | None, int]:
    if previous_score is None:
        updated_count = rating_count + 1
        if updated_count <= 0:
            return None, 0
        running_total = (average_rating or 0.0) * rating_count
        return (running_total + submitted_score) / updated_count, updated_count

    if rating_count <= 0:
        return float(submitted_score), 1

    running_total = (average_rating or 0.0) * rating_count
    return (running_total - previous_score + submitted_score) / rating_count, rating_count


def _serialize_playground_target_options(targets) -> list[PlaygroundTargetOptionPayload]:
    serialized_targets: list[PlaygroundTargetOptionPayload] = []
    for target in targets:
        serialized_targets.append(
            {
                "id": target.id,
                "label": target.label,
                "playground_id": target.playground_id,
                "option_label": _build_saved_target_option_label(target),
                "helper_label": _build_saved_target_helper_label(target),
                "is_default": target.is_default,
            }
        )
    return serialized_targets


def _build_saved_target_option_label(target) -> str:
    if target.is_default:
        return f"{target.label} / {target.playground_id} / Default"
    return f"{target.label} / {target.playground_id}"


def _build_saved_target_helper_label(target) -> str:
    if target.last_used_at is None:
        prefix = "Never used"
    else:
        prefix = f"Last used {format_contract_calendar_date(target.last_used_at)}"
    if target.is_default:
        return f"{prefix} / Default target"
    return prefix


def _format_saved_target_count_label(count: int) -> str:
    return "1 saved target" if count == 1 else f"{count} saved targets"


def _default_saved_target_id(targets: list[PlaygroundTargetOptionPayload]) -> str:
    if not targets:
        return ""
    return str(targets[0]["id"])


def _saved_target_id_exists(
    *,
    saved_target_id: str,
    targets: list[PlaygroundTargetOptionPayload],
) -> bool:
    if not saved_target_id:
        return False
    return any(str(target["id"]) == saved_target_id for target in targets)


def _resolve_deployment_version(
    *,
    selected_version: str,
    available_versions: list[VersionHistoryPayload],
) -> str:
    normalized_selected_version = selected_version.strip()
    if normalized_selected_version:
        return normalized_selected_version
    if not available_versions:
        return ""
    return available_versions[0]["semantic_version"]


def _normalize_deployment_target_mode(
    value: str,
    *,
    has_saved_targets: bool,
) -> str:
    if has_saved_targets and value == DEPLOYMENT_TARGET_MODE_SAVED:
        return DEPLOYMENT_TARGET_MODE_SAVED
    return DEPLOYMENT_TARGET_MODE_AD_HOC


def _deployment_status_label(status: DeploymentStatus) -> str:
    if status is DeploymentStatus.REDIRECT_REQUIRED:
        return "Redirect ready"
    if status is DeploymentStatus.ACCEPTED:
        return "Accepted"
    return "Failed"


def _deployment_status_color_scheme(status: DeploymentStatus) -> str:
    if status is DeploymentStatus.FAILED:
        return "tomato"
    return "bronze"


def _format_deployment_transport_label(transport: DeploymentTransport | None) -> str:
    if transport is None:
        return ""
    if transport is DeploymentTransport.DEEP_LINK:
        return "Deep link"
    if transport is DeploymentTransport.HTTP:
        return "HTTP"
    return "Hybrid"


def _build_deployment_result_message(result: ContractDeploymentAttemptResult) -> str:
    if result.status is DeploymentStatus.REDIRECT_REQUIRED:
        return "Deployment recorded. Open the playground to continue."
    if result.status is DeploymentStatus.ACCEPTED:
        return "Deployment accepted."
    return _build_deployment_failure_message(result)


def _build_deployment_failure_message(result: ContractDeploymentAttemptResult) -> str:
    error_code = ""
    if result.error_payload is not None:
        error_code = str(result.error_payload.get("code", "")).strip()
    mapped_messages = {
        "adapter_misconfigured": "Deployment is unavailable right now.",
        "invalid_contract_name": "This contract cannot be deployed right now.",
        "invalid_playground_id": "This playground target could not be accepted.",
        "invalid_source": "This version cannot be deployed because its source is invalid.",
        "payload_rejected": "The playground rejected this deployment request.",
        "timeout": "The deployment request timed out. Try again.",
        "unavailable": "The playground is temporarily unavailable. Try again.",
    }
    return mapped_messages.get(error_code, result.message or "Deployment failed.")


def _build_deployment_result_detail(result: ContractDeploymentAttemptResult) -> str:
    return (
        f"Deployment #{result.deployment_id} / Version {result.semantic_version} "
        f"/ Playground {result.playground_id}"
    )


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
