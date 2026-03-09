from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
import sqlalchemy as sa
from reflex.model import ModelRegistry
from sqlmodel import Session

from contracting_hub.config import sqlite_url_for_path
from contracting_hub.models import (
    Category,
    Contract,
    ContractCategoryLink,
    ContractNetwork,
    ContractRelation,
    ContractRelationType,
    Profile,
    PublicationStatus,
    Rating,
    Star,
    User,
)
from contracting_hub.services import create_contract_version


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict[str, bool]:
    """Keep browser-backed E2E runs headless in automated loops."""
    return {"headless": True}


@pytest.fixture(scope="session")
def browser_context_args(
    browser_context_args: dict[str, object],
) -> dict[str, object]:
    """Apply a stable viewport for browser tests across local and CI runs."""
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 960},
    }


def _timestamp(day: int) -> datetime:
    return datetime(2026, 2, day, 12, 0, tzinfo=timezone.utc)


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _configure_sqlite_engine(engine: sa.Engine) -> None:
    @sa.event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _build_seed_engine(database_path: Path) -> sa.Engine:
    engine = sa.create_engine(sqlite_url_for_path(database_path))
    _configure_sqlite_engine(engine)
    ModelRegistry.get_metadata().create_all(engine)
    return engine


def _seed_public_catalog(session: Session) -> None:
    alice = User(email="alice@example.com", password_hash="hashed-password")
    alice.profile = Profile(
        username="alice",
        display_name="Alice Validator",
        bio="Builds reusable escrow releases for treasury teams.",
        website_url="https://alice.dev",
        github_url="https://github.com/alice",
    )
    bob = User(email="bob@example.com", password_hash="hashed-password")
    bob.profile = Profile(username="bob", display_name="Bob Review")
    charlie = User(email="charlie@example.com", password_hash="hashed-password")
    charlie.profile = Profile(username="charlie", display_name="Charlie Curator")
    dana = User(email="dana@example.com", password_hash="hashed-password")
    dana.profile = Profile(username="dana", display_name="Dana Ops")

    defi = Category(slug="defi", name="DeFi", sort_order=10)
    security = Category(slug="security", name="Security", sort_order=20)
    tooling = Category(slug="tooling", name="Tooling", sort_order=30)

    escrow = Contract(
        slug="escrow",
        contract_name="con_escrow",
        display_name="Escrow",
        short_summary="Curated escrow settlement primitives.",
        long_description="Detailed escrow flows for staged settlement and release review.",
        author=alice,
        status=PublicationStatus.PUBLISHED,
        featured=True,
        license_name="MIT",
        documentation_url="https://docs.example.com/escrow",
        source_repository_url="https://github.com/example/escrow",
        network=ContractNetwork.SANDBOX,
        tags=["escrow", "settlement"],
        created_at=_timestamp(2),
        updated_at=_timestamp(8),
    )
    escrow_tools = Contract(
        slug="escrow-tools",
        contract_name="con_escrow_tools",
        display_name="Escrow Toolkit",
        short_summary="Tooling for escrow audits.",
        long_description="Support utilities for inspecting escrow state transitions.",
        author=bob,
        status=PublicationStatus.PUBLISHED,
        tags=["escrow", "utilities"],
        created_at=_timestamp(3),
        updated_at=_timestamp(7),
    )
    vault = Contract(
        slug="vault",
        contract_name="con_vault",
        display_name="Vault",
        short_summary="Treasury vault reference.",
        long_description="Security-focused custody primitives for shared treasury flows.",
        author_label="Core Team",
        status=PublicationStatus.PUBLISHED,
        tags=["treasury", "security"],
        created_at=_timestamp(4),
        updated_at=_timestamp(6),
    )
    draft_escrow = Contract(
        slug="draft-escrow",
        contract_name="con_draft_escrow",
        display_name="Draft Escrow",
        short_summary="Draft canary for browse visibility coverage.",
        long_description="Draft-only entry that should never appear publicly.",
        status=PublicationStatus.DRAFT,
        tags=["escrow", "draft"],
        created_at=_timestamp(5),
        updated_at=_timestamp(9),
    )

    session.add_all(
        [
            alice,
            bob,
            charlie,
            dana,
            defi,
            security,
            tooling,
            escrow,
            escrow_tools,
            vault,
            draft_escrow,
            ContractCategoryLink(contract=escrow, category=defi, is_primary=True),
            ContractCategoryLink(contract=escrow_tools, category=tooling, is_primary=True),
            ContractCategoryLink(contract=vault, category=security, is_primary=True),
            ContractCategoryLink(contract=draft_escrow, category=defi, is_primary=True),
        ]
    )
    session.commit()

    create_contract_version(
        session=session,
        contract_slug="escrow",
        semantic_version="1.0.0",
        source_code="@export\ndef settle_release_path():\n    return 'legacy escrow'\n",
        changelog="Legacy public release.",
        status=PublicationStatus.DEPRECATED,
    )
    create_contract_version(
        session=session,
        contract_slug="escrow",
        semantic_version="1.1.0",
        source_code="@export\ndef settle_release_path():\n    return 'draft escrow'\n",
        changelog="Draft-only release.",
        status=PublicationStatus.DRAFT,
    )
    create_contract_version(
        session=session,
        contract_slug="escrow",
        semantic_version="2.0.0",
        source_code="@export\ndef settle_release_path():\n    return 'released escrow'\n",
        changelog="Current public release.",
        status=PublicationStatus.PUBLISHED,
    )
    create_contract_version(
        session=session,
        contract_slug="escrow-tools",
        semantic_version="1.0.0",
        source_code="@export\ndef inspect_escrow_state():\n    return 'tools'\n",
        changelog="Initial tooling release.",
        status=PublicationStatus.PUBLISHED,
    )
    create_contract_version(
        session=session,
        contract_slug="vault",
        semantic_version="1.0.0",
        source_code="@export\ndef treasury_guard_marker():\n    return 'vault'\n",
        changelog="Initial vault release.",
        status=PublicationStatus.PUBLISHED,
    )
    create_contract_version(
        session=session,
        contract_slug="draft-escrow",
        semantic_version="0.1.0",
        source_code="@export\ndef hidden_draft_canary():\n    return 'draft'\n",
        changelog="Hidden draft release.",
        status=PublicationStatus.DRAFT,
    )

    session.add_all(
        [
            Star(user_id=bob.id, contract_id=escrow.id),
            Star(user_id=charlie.id, contract_id=escrow.id),
            Star(user_id=charlie.id, contract_id=escrow_tools.id),
            Star(user_id=alice.id, contract_id=vault.id),
            Star(user_id=bob.id, contract_id=vault.id),
            Star(user_id=charlie.id, contract_id=vault.id),
            Star(user_id=dana.id, contract_id=vault.id),
            Rating(user_id=bob.id, contract_id=escrow.id, score=5),
            Rating(user_id=charlie.id, contract_id=escrow.id, score=4),
            Rating(user_id=alice.id, contract_id=vault.id, score=5),
            ContractRelation(
                source_contract_id=escrow.id,
                target_contract_id=vault.id,
                relation_type=ContractRelationType.COMPANION,
            ),
        ]
    )
    session.commit()


def _resolve_reflex_binary(project_root: Path) -> str:
    venv_binary = project_root / ".venv" / "bin" / "reflex"
    if venv_binary.exists():
        return str(venv_binary)

    installed_binary = shutil.which("reflex")
    if installed_binary is not None:
        return installed_binary

    raise RuntimeError("Could not find a reflex executable for Playwright E2E tests.")


def _tail_log(log_path: Path, *, max_chars: int = 12000) -> str:
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8")[-max_chars:]


def _wait_for_server(
    *,
    process: subprocess.Popen[str],
    url: str,
    log_path: Path,
    timeout_seconds: float = 120.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Reflex app exited before it became ready.\n\n{_tail_log(log_path)}"
            )
        try:
            with urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except URLError:
            time.sleep(1)
            continue

    raise RuntimeError(f"Timed out waiting for the Reflex app to start.\n\n{_tail_log(log_path)}")


def _stop_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    if hasattr(os, "killpg"):
        os.killpg(process.pid, signal.SIGTERM)
    else:
        process.terminate()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=5)


@pytest.fixture(scope="session")
def live_server_url(project_root: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Launch a real Reflex app against deterministic public catalog data."""
    working_dir = tmp_path_factory.mktemp("e2e_reflex_app")
    database_path = working_dir / "contracting_hub_e2e.db"
    uploads_dir = working_dir / "uploads"
    instance_dir = working_dir / "instance"
    log_path = working_dir / "reflex-app.log"
    engine = _build_seed_engine(database_path)

    with Session(engine) as session:
        _seed_public_catalog(session)
    engine.dispose()

    port = _find_free_port()
    app_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "CONTRACTING_HUB_ENV": "e2e",
            "CONTRACTING_HUB_DB_PATH": str(database_path),
            "CONTRACTING_HUB_INSTANCE_DIR": str(instance_dir),
            "CONTRACTING_HUB_UPLOADS_DIR": str(uploads_dir),
            "REFLEX_DB_URL": sqlite_url_for_path(database_path),
        }
    )

    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            _resolve_reflex_binary(project_root),
            "run",
            "--env",
            "prod",
            "--single-port",
            "--frontend-port",
            str(port),
            "--backend-port",
            str(port),
            "--loglevel",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )

    try:
        _wait_for_server(process=process, url=app_url, log_path=log_path)
        yield app_url
    finally:
        _stop_process_group(process)
        log_handle.close()
