"""Smoke tests for the aqao-api Helm chart — Story 3.6.2.

A real `helm template + kubeconform` round-trip needs the helm binary,
which we don't assume is available on the dev machine. These tests
parse the chart's YAML files directly and assert the security
primitives the PSS "restricted" profile cares about are actually set.

If a future PR turns off `runAsNonRoot` or removes the `cap-drop`,
these tests fail loud.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CHART_ROOT = Path(__file__).resolve().parents[3] / "infra" / "helm" / "aqao-api"


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- chart layout


def test_chart_root_exists() -> None:
    assert CHART_ROOT.is_dir(), CHART_ROOT


def test_chart_yaml_declares_metadata() -> None:
    chart = _load_yaml(CHART_ROOT / "Chart.yaml")
    assert chart["name"] == "aqao-api"
    assert chart["apiVersion"] == "v2"
    assert chart["type"] == "application"
    assert chart.get("kubeVersion", "").startswith(">=1.27")


def test_required_templates_are_present() -> None:
    """Every primitive the README promises must have a template."""
    expected = {
        "_helpers.tpl",
        "deployment.yaml",
        "service.yaml",
        "serviceaccount.yaml",
        "hpa.yaml",
        "pdb.yaml",
        "networkpolicy.yaml",
        "ingress.yaml",
        "servicemonitor.yaml",
    }
    actual = {p.name for p in (CHART_ROOT / "templates").iterdir()}
    missing = expected - actual
    assert not missing, f"missing templates: {missing}"


# ---------------------------------------------------------------- values.yaml


def test_values_security_defaults_match_pss_restricted() -> None:
    values = _load_yaml(CHART_ROOT / "values.yaml")

    pod_sec = values["podSecurityContext"]
    assert pod_sec["runAsNonRoot"] is True
    assert pod_sec["runAsUser"] >= 10000  # non-zero, non-system UID
    assert pod_sec["seccompProfile"]["type"] == "RuntimeDefault"

    container_sec = values["containerSecurityContext"]
    assert container_sec["runAsNonRoot"] is True
    assert container_sec["readOnlyRootFilesystem"] is True
    assert container_sec["allowPrivilegeEscalation"] is False
    assert "ALL" in container_sec["capabilities"]["drop"]


def test_values_have_hpa_pdb_and_networkpolicy_enabled_by_default() -> None:
    """The chart README promises these primitives are on by default —
    a values regression that disables one of them is a security
    regression."""
    values = _load_yaml(CHART_ROOT / "values.yaml")
    assert values["autoscaling"]["enabled"] is True
    assert values["podDisruptionBudget"]["enabled"] is True
    assert values["networkPolicy"]["enabled"] is True


def test_values_probes_cover_all_three_lifecycle_stages() -> None:
    values = _load_yaml(CHART_ROOT / "values.yaml")
    probes = values["probes"]
    for stage in ("liveness", "readiness", "startup"):
        assert stage in probes, stage
        assert probes[stage]["path"].startswith("/")


def test_values_resource_limits_are_set() -> None:
    values = _load_yaml(CHART_ROOT / "values.yaml")
    resources = values["resources"]
    assert "cpu" in resources["requests"]
    assert "memory" in resources["requests"]
    assert "cpu" in resources["limits"]
    assert "memory" in resources["limits"]


# ---------------------------------------------------------------- per-template structural


def test_deployment_template_references_security_context_blocks() -> None:
    """Even without rendering, the template should reference both the
    pod-level and container-level security contexts so the values
    above are actually applied."""
    body = (CHART_ROOT / "templates" / "deployment.yaml").read_text(encoding="utf-8")
    assert ".Values.podSecurityContext" in body
    assert ".Values.containerSecurityContext" in body
    assert "checksum/values" in body  # rolls pods on config change


def test_networkpolicy_template_denies_by_default_for_egress() -> None:
    body = (CHART_ROOT / "templates" / "networkpolicy.yaml").read_text(encoding="utf-8")
    # Both directions in policyTypes -> deny-by-default unless an
    # explicit ingress/egress rule allows.
    assert "policyTypes:" in body
    assert "Ingress" in body
    assert "Egress" in body


def test_pdb_template_uses_min_available_one() -> None:
    body = (CHART_ROOT / "templates" / "pdb.yaml").read_text(encoding="utf-8")
    assert "minAvailable" in body
    values = _load_yaml(CHART_ROOT / "values.yaml")
    assert values["podDisruptionBudget"]["minAvailable"] >= 1


# ---------------------------------------------------------------- terraform smoke


def test_terraform_modules_have_versions_pinned() -> None:
    """Story 3.6.1 — every module declares required_version + an
    `aws` provider pin so a future `terraform init` is reproducible."""
    tf_root = CHART_ROOT.parents[1] / "terraform"
    main_files = list(tf_root.glob("modules/*/main.tf"))
    assert main_files, "expected at least one terraform module"
    for path in main_files:
        body = path.read_text(encoding="utf-8")
        assert "required_version" in body, f"{path} missing required_version"
        assert "hashicorp/aws" in body, f"{path} missing aws provider pin"


def test_terraform_dev_environment_composes_every_module() -> None:
    main = (CHART_ROOT.parents[1] / "terraform" / "environments" / "dev" / "main.tf").read_text(
        encoding="utf-8"
    )
    for module_name in ("vpc", "eks", "rds", "redis", "evidence", "secrets", "iam"):
        assert f'module "{module_name}"' in main, module_name
