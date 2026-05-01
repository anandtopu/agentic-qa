"""Smoke tests for Phase-5 docs + SDKs — Stories 5.1 / 5.2 / 5.3.

Covers:

* User docs cover all five core pages + FAQ + Troubleshooting.
* Operator docs cover install (local + cloud) + upgrade + backup +
  monitoring + troubleshooting.
* API reference + Python + TypeScript SDK doc pages exist and
  cross-link.
* Python SDK: client builds + dispatches through the injected
  sender + raises the right error subclass per status code.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(*parts: str) -> str:
    return (REPO_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


# ---------------------------------------------------------------- user docs


@pytest.mark.parametrize(
    "name",
    [
        "index.md",
        "getting-started.md",
        "policy.md",
        "github-action.md",
        "approvals.md",
        "reading-the-run.md",
        "faq.md",
        "troubleshooting.md",
    ],
)
def test_user_doc_page_exists(name: str) -> None:
    assert (REPO_ROOT / "docs" / "user" / name).is_file()


def test_user_index_links_to_each_step() -> None:
    body = _read("docs", "user", "index.md")
    for slug in (
        "getting-started.md",
        "policy.md",
        "github-action.md",
        "approvals.md",
        "reading-the-run.md",
    ):
        assert slug in body, slug


def test_user_index_promises_30_minute_target() -> None:
    """AC: first-run user reaches a green run in ≤ 30 min."""
    body = _read("docs", "user", "index.md")
    assert "30 min" in body or "30 minutes" in body


# ---------------------------------------------------------------- operator docs


@pytest.mark.parametrize(
    "name",
    [
        "index.md",
        "install-local.md",
        "install-cloud.md",
        "install-aws.md",
        "install-gcp.md",
        "upgrade.md",
        "backup-restore.md",
        "monitoring.md",
        "troubleshooting.md",
    ],
)
def test_operator_doc_page_exists(name: str) -> None:
    assert (REPO_ROOT / "docs" / "operator" / name).is_file()


def test_operator_install_cloud_links_to_provider_runbooks() -> None:
    """The chooser page must point at both AWS and GCP step-by-steps."""
    body = _read("docs", "operator", "install-cloud.md")
    assert "install-aws.md" in body
    assert "install-gcp.md" in body


def test_operator_install_aws_references_terraform_and_helm() -> None:
    """The AWS install flow ties Story 3.6.1 + 3.6.2 together."""
    body = _read("docs", "operator", "install-aws.md").lower()
    assert "terraform apply" in body
    assert "helm upgrade" in body
    assert "kubectl" in body
    assert "irsa" in body  # workload identity binding


def test_operator_install_gcp_references_gcloud_and_helm() -> None:
    """GCP runbook drives gcloud directly + uses the same Helm chart."""
    body = _read("docs", "operator", "install-gcp.md").lower()
    assert "gcloud container clusters create" in body
    assert "workload identity" in body
    assert "cloud sql" in body
    assert "secret manager" in body
    assert "helm" in body


def test_operator_backup_links_to_dr_runbook() -> None:
    body = _read("docs", "operator", "backup-restore.md")
    assert "disaster-recovery.md" in body


def test_operator_monitoring_lists_default_slos() -> None:
    body = _read("docs", "operator", "monitoring.md")
    for slo in ("API availability", "PR analysis", "Eval success rate"):
        assert slo in body


# ---------------------------------------------------------------- api reference


@pytest.mark.parametrize(
    "name",
    ["index.md", "python.md", "typescript.md"],
)
def test_api_reference_page_exists(name: str) -> None:
    assert (REPO_ROOT / "docs" / "api" / name).is_file()


def test_api_index_lists_every_resource_group() -> None:
    body = _read("docs", "api", "index.md")
    for group in (
        "/api/v1/workspaces",
        "/api/v1/test-runs",
        "/api/v1/approvals",
        "/api/v1/audit",
        "/api/v1/usage",
    ):
        assert group in body, group


# ---------------------------------------------------------------- python sdk


def test_python_sdk_layout_present() -> None:
    sdk = REPO_ROOT / "sdks" / "python" / "aqao_sdk"
    assert (sdk / "__init__.py").is_file()
    assert (sdk / "client.py").is_file()
    assert (sdk / "errors.py").is_file()
    assert (sdk / "py.typed").is_file()
    assert (REPO_ROOT / "sdks" / "python" / "pyproject.toml").is_file()


def test_python_sdk_client_dispatches_through_injected_sender() -> None:
    sys.path.insert(0, str(REPO_ROOT / "sdks" / "python"))
    try:
        from aqao_sdk import AQAOClient

        recorded: dict[str, Any] = {}

        def stub_sender(**kwargs: Any) -> dict[str, Any]:
            recorded.update(kwargs)
            return {"id": "ws-1", "name": "Payments"}

        client = AQAOClient(
            base_url="https://api.aqao.ai",
            token="t",
            tenant_id="aaaa",
            role="engineer",
            sender=stub_sender,
        )
        out = client.workspaces.create(name="Payments", application_type="web_api")
        assert out["id"] == "ws-1"
        assert recorded["method"] == "POST"
        assert recorded["url"].endswith("/api/v1/workspaces")
        assert recorded["headers"]["Authorization"] == "Bearer t"
        assert recorded["headers"]["X-AQAO-Tenant-Id"] == "aaaa"
        assert recorded["headers"]["X-AQAO-Role"] == "engineer"
        assert "Idempotency-Key" in recorded["headers"]
    finally:
        sys.path.pop(0)


def test_python_sdk_error_for_status_dispatches_correct_subclass() -> None:
    sys.path.insert(0, str(REPO_ROOT / "sdks" / "python"))
    try:
        from aqao_sdk.errors import (
            AQAOError,
            AuthError,
            ConflictError,
            NotFoundError,
            PermissionError_,
            RateLimitError,
            ValidationError,
            error_for_status,
        )

        def make(status: int, **kw: Any) -> AQAOError:
            return error_for_status(
                status_code=status,
                message="x",
                trace_id="t",
                details=None,
                **kw,
            )

        assert isinstance(make(401), AuthError)
        assert isinstance(make(403), PermissionError_)
        assert isinstance(make(404), NotFoundError)
        assert isinstance(make(409), ConflictError)
        assert isinstance(make(422), ValidationError)
        rl = make(429, retry_after_seconds=5.0)
        assert isinstance(rl, RateLimitError)
        assert rl.retry_after_seconds == 5.0
        # Unknown status falls back to the base class.
        assert type(make(500)) is AQAOError
    finally:
        sys.path.pop(0)


# ---------------------------------------------------------------- typescript sdk


def test_typescript_sdk_layout_present() -> None:
    sdk = REPO_ROOT / "sdks" / "typescript"
    assert (sdk / "package.json").is_file()
    assert (sdk / "tsconfig.json").is_file()
    assert (sdk / "src" / "index.ts").is_file()
    assert (sdk / "src" / "client.ts").is_file()
    assert (sdk / "src" / "errors.ts").is_file()


def test_typescript_sdk_uses_strict_typescript() -> None:
    body = _read("sdks", "typescript", "tsconfig.json")
    # Strict mode + the extras we promised (noUncheckedIndexedAccess,
    # exactOptionalPropertyTypes) are part of the contract.
    for opt in (
        '"strict": true',
        '"noUncheckedIndexedAccess": true',
        '"exactOptionalPropertyTypes": true',
    ):
        assert opt in body, opt


def test_typescript_sdk_targets_node_18_plus() -> None:
    body = _read("sdks", "typescript", "package.json")
    assert '"node": ">=18"' in body
