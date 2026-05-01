"""GitHub PR diff parser.

GitHub webhook payloads carry the PR metadata (changed files, base/head,
SHAs) but not the unified diff text — that's fetched separately when an
agent needs it. This parser captures the metadata; Story 1.9 (PR
analysis) will lazy-fetch the diff body when the Planner asks for it.
"""

from __future__ import annotations

from typing import Any

from aqao_api.requirements.parsers.base import ParsedRequirement, ParseError


def parse(raw: dict[str, Any]) -> ParsedRequirement:
    """Accept either a raw GitHub webhook body or a pre-shaped manual payload.

    Manual payload shape::

        {"action": "opened", "pr_number": 42, "commit_sha": "abc...",
         "changed_files": ["a.py", "b.py"], "base_branch": "main",
         "head_branch": "feature/x"}
    """
    action = raw.get("action")
    pr = raw.get("pull_request") or raw
    if not isinstance(pr, dict):
        raise ParseError("pull_request payload missing", field="pull_request")

    pr_number = pr.get("number") or raw.get("pr_number")
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    commit_sha = raw.get("commit_sha") or (head.get("sha") if isinstance(head, dict) else None)
    head_branch = (head.get("ref") if isinstance(head, dict) else None) or raw.get("head_branch")
    base_branch = (base.get("ref") if isinstance(base, dict) else None) or raw.get("base_branch")
    title = pr.get("title") or raw.get("title")
    body = pr.get("body") or raw.get("body")
    changed_files = raw.get("changed_files")
    if changed_files is not None and not isinstance(changed_files, list):
        raise ParseError("changed_files must be a list", field="changed_files")

    if pr_number is None or commit_sha is None:
        raise ParseError(
            "PR diff payload requires pr_number and commit_sha",
            field="pr_number",
        )

    repo = pr.get("base", {}).get("repo", {}) if isinstance(base, dict) else {}
    full_name = (repo.get("full_name") if isinstance(repo, dict) else None) or raw.get(
        "repository_full_name"
    )

    summary_parts = [f"PR #{pr_number}"]
    if title:
        summary_parts.append(f"— {title}")
    if action:
        summary_parts.append(f"({action})")

    return ParsedRequirement(
        summary=" ".join(summary_parts),
        commit_sha=str(commit_sha),
        source_ref=f"{full_name}#PR{pr_number}" if full_name else f"PR#{pr_number}",
        payload={
            "action": action,
            "pr_number": int(pr_number),
            "title": title,
            "body": body,
            "head_branch": head_branch,
            "base_branch": base_branch,
            "commit_sha": str(commit_sha),
            "repository_full_name": full_name,
            "changed_files": list(changed_files or []),
        },
    )
