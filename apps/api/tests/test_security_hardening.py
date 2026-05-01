"""Security-hardening artifacts + Jira sig verification — Epic 4.4.

Covers:

* Threat-model document exists and enumerates every STRIDE category.
* CI security workflow declares the four required jobs (semgrep,
  trivy-fs, zap-baseline, sbom-and-sign) and uses pinned action SHAs
  / version tags.
* Jira webhook signature verification is constant-time HMAC-SHA256.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from pathlib import Path

import yaml

from aqao_api.webhooks.jira_signing import (
    JIRA_SIGNATURE_HEADER,
    verify_jira_signature,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------- threat model


def test_threat_model_document_exists() -> None:
    doc = REPO_ROOT / "docs" / "security" / "threat-model.md"
    assert doc.is_file(), doc


def test_threat_model_covers_every_stride_category() -> None:
    body = (REPO_ROOT / "docs" / "security" / "threat-model.md").read_text(encoding="utf-8")
    for category in (
        "Spoofing",
        "Tampering",
        "Repudiation",
        "Information disclosure",
        "Denial of service",
        "Elevation of privilege",
    ):
        assert category in body, category


def test_threat_model_references_existing_stories() -> None:
    """Every mitigation should cite the story that delivered it —
    keeps the doc honest as the codebase changes."""
    body = (REPO_ROOT / "docs" / "security" / "threat-model.md").read_text(encoding="utf-8")
    for story in ("2.4.1", "3.1.1", "3.6.1", "3.6.2", "4.3"):
        assert story in body, story


# ---------------------------------------------------------------- CI workflow


def _load_workflow() -> dict[str, object]:
    return yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    )


def test_security_workflow_declares_required_jobs() -> None:
    workflow = _load_workflow()
    jobs = workflow["jobs"]  # type: ignore[index]
    assert isinstance(jobs, dict)
    for required in ("semgrep", "trivy-fs", "zap-baseline", "sbom-and-sign"):
        assert required in jobs, required


def test_security_workflow_runs_on_pr_push_and_nightly() -> None:
    workflow = _load_workflow()
    # YAML 1.1 quirk: bare `on:` parses as the boolean True. Look up
    # via either key.
    triggers = workflow.get("on") or workflow.get(True)  # type: ignore[arg-type]
    assert isinstance(triggers, dict), triggers
    assert "push" in triggers
    assert "pull_request" in triggers
    assert "schedule" in triggers


def test_security_workflow_pins_action_versions() -> None:
    """Float `@main` action references would be a security regression;
    every action must use a `@vX` tag or commit SHA."""
    body = (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    # Find every `uses:` and assert it does NOT end in `@main` /
    # `@master` / no version.
    bad: list[str] = []
    for match in re.finditer(r"uses:\s*([^\s]+)", body):
        ref = match.group(1)
        if "@" not in ref:
            bad.append(ref + " (no version)")
            continue
        version = ref.rsplit("@", 1)[1]
        if version.lower() in {"main", "master", "head"}:
            bad.append(ref)
    assert not bad, f"unpinned action refs: {bad}"


def test_security_workflow_includes_cosign_signing_step() -> None:
    body = (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    assert "cosign sign" in body
    assert "cosign attest" in body  # SBOM attestation


def test_security_workflow_uploads_sarif_for_sast_and_sca() -> None:
    body = (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    # Both Semgrep and Trivy upload SARIF so findings land in the
    # GitHub Security tab.
    assert body.count("upload-sarif@v3") >= 2


# ---------------------------------------------------------------- Jira HMAC


def _sig(secret: str, body: bytes) -> str:
    return (
        "sha256=" + hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()
    )


def test_jira_signature_verifies_a_correct_signature() -> None:
    body = b'{"webhookEvent":"jira:issue_updated"}'
    secret = "supersecret"
    assert verify_jira_signature(secret=secret, body=body, header_value=_sig(secret, body))


def test_jira_signature_rejects_wrong_secret() -> None:
    body = b'{"webhookEvent":"jira:issue_updated"}'
    bad_sig = _sig("attacker", body)
    assert not verify_jira_signature(secret="supersecret", body=body, header_value=bad_sig)


def test_jira_signature_rejects_missing_header() -> None:
    assert not verify_jira_signature(secret="supersecret", body=b"{}", header_value=None)


def test_jira_signature_rejects_unprefixed_header() -> None:
    body = b"{}"
    secret = "supersecret"
    raw_hex = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()
    # Header without the `sha256=` prefix must fail closed.
    assert not verify_jira_signature(secret=secret, body=body, header_value=raw_hex)


def test_jira_signature_constant_time_compare_via_hmac_module() -> None:
    """Smoke-check the impl uses hmac.compare_digest, not == — a
    timing-attack regression would re-introduce ==."""
    src = (
        REPO_ROOT / "apps" / "api" / "src" / "aqao_api" / "webhooks" / "jira_signing.py"
    ).read_text(encoding="utf-8")
    assert "hmac.compare_digest" in src


def test_jira_signature_header_constant_is_canonical_name() -> None:
    assert JIRA_SIGNATURE_HEADER == "X-Hub-Signature-256"


# ---------------------------------------------------------------- redactor still in place


def test_redactor_module_still_exposed() -> None:
    """Information-disclosure mitigations rely on the redactor —
    verify the public import surface didn't drift away from the
    threat-model expectations."""
    from aqao_redaction import default_redactor

    assert default_redactor is not None


# ---------------------------------------------------------------- SBOM gate


def test_sbom_artifact_uploaded_in_workflow() -> None:
    body = (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    # CycloneDX is the format the Helm chart README + threat model
    # promise; lock it down here so a regression is loud.
    assert "cyclonedx" in body.lower()
    assert "sbom.cdx.json" in body


# ---------------------------------------------------------------- ZAP rules


def test_zap_rules_file_exists_and_is_tab_separated() -> None:
    rules = REPO_ROOT / ".zap" / "rules.tsv"
    assert rules.is_file()
    for line in rules.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        # Each rule line has at least 3 tab-separated columns:
        # rule_id, action, url_regex (parameter is optional).
        assert "\t" in line
