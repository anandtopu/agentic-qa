"""Unit tests for the heuristic open-question detector — Story 1.3.2."""

from __future__ import annotations

from aqao_agents.planner.ambiguity import detect_open_questions


def _case(
    *,
    title: str = "Happy path",
    type: str = "api",  # noqa: A002
    expected_result: str = "200 OK",
) -> dict[str, object]:
    return {
        "title": title,
        "type": type,
        "expected_result": expected_result,
    }


def test_detects_vague_qualifiers() -> None:
    out = detect_open_questions(
        requirement_summary="Make the checkout fast",
        parsed_payload={"body": "Checkout should be fast and handle errors."},
        test_cases=[_case()],
    )
    joined = "\n".join(out)
    assert "fast" in joined.lower() or "performance" in joined.lower()


def test_flags_missing_negative_path() -> None:
    out = detect_open_questions(
        requirement_summary="POST /charge",
        parsed_payload={"endpoints": [{"path": "/charge", "method": "post"}]},
        test_cases=[_case(type="api", expected_result="200 OK")],
    )
    assert any("negative" in q.lower() for q in out)


def test_does_not_flag_when_negative_case_present() -> None:
    out = detect_open_questions(
        requirement_summary="POST /charge",
        parsed_payload={},
        test_cases=[
            _case(),
            _case(
                title="Invalid card returns 422",
                type="negative",
                expected_result="422 with validation error",
            ),
        ],
    )
    assert not any("negative" in q.lower() for q in out)


def test_flags_missing_auth_failure_case_when_auth_referenced() -> None:
    out = detect_open_questions(
        requirement_summary="OAuth login flow",
        parsed_payload={"body": "User logs in with password"},
        test_cases=[
            _case(title="Successful login", expected_result="redirect to /home"),
            _case(
                title="Invalid CSRF",
                type="negative",
                expected_result="403 forbidden",
            ),
        ],
    )
    assert any("auth" in q.lower() for q in out)


def test_does_not_flag_auth_when_auth_failure_case_present() -> None:
    out = detect_open_questions(
        requirement_summary="OAuth login flow",
        parsed_payload={"body": "User logs in"},
        test_cases=[
            _case(title="Successful login", expected_result="redirect"),
            _case(
                title="Auth fail wrong password",
                type="negative",
                expected_result="401 returned",
            ),
        ],
    )
    auth_questions = [
        q
        for q in out
        if "authn-failure" in q.lower() or ("auth" in q.lower() and "fail" in q.lower())
    ]
    assert not auth_questions
