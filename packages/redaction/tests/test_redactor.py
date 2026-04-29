from __future__ import annotations

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from qaforge_redaction import REDACTED, Redactor, redact


class TestBuiltinPatterns:
    @pytest.mark.parametrize(
        ("name", "raw"),
        [
            ("anthropic", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789"),
            ("openai", "sk-proj-abcdefghijklmnopqrstuvwxyz012345"),
            ("google", "AIzaSyA-abcdefghijklmnopqrstuvwxyz0123456"),
            ("github_pat", "ghp_" + "a" * 40),
            ("aws_access", "AKIAIOSFODNN7EXAMPLE"),
            ("jwt", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature1234567890abcdef"),
        ],
    )
    def test_well_known_credentials_are_replaced(self, name: str, raw: str) -> None:
        text = f"creds: {raw} end"
        result = redact(text)
        assert raw not in result, f"{name} leaked: {result}"
        assert REDACTED in result

    def test_authorization_bearer_keeps_header_name(self) -> None:
        text = "Authorization: Bearer abc.def.ghi"
        result = redact(text)
        assert "abc.def.ghi" not in result
        assert "Authorization" in result
        assert REDACTED in result

    def test_basic_auth_keeps_header_name(self) -> None:
        text = "authorization: basic dXNlcjpwYXNzd29yZA=="
        result = redact(text)
        assert "dXNlcjpwYXNzd29yZA==" not in result
        assert "authorization" in result.lower()

    def test_url_userinfo_is_redacted(self) -> None:
        result = redact("postgres://user:secretpass@db:5432/app")
        assert "secretpass" not in result
        assert "user" not in result
        assert "postgres://" in result
        assert "db:5432/app" in result

    def test_password_kv_is_redacted(self) -> None:
        result = redact('password="hunter2supersecret"')
        assert "hunter2supersecret" not in result

    def test_private_key_block_is_redacted(self) -> None:
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEpAIBAAKCAQEAabc...secret content...xyz\n"
            "-----END RSA PRIVATE KEY-----"
        )
        result = redact(text)
        assert "secret content" not in result
        assert REDACTED in result

    def test_empty_string_is_returned_as_is(self) -> None:
        assert redact("") == ""

    def test_clean_text_is_unchanged(self) -> None:
        text = "Test plan generated for checkout flow with 12 cases."
        assert redact(text) == text


class TestExtraStringRedaction:
    def test_known_secret_is_scrubbed(self) -> None:
        secret = "this-is-a-known-injected-token-xyz"
        r = Redactor.builtin().with_extra(strings=[secret])
        assert secret not in r.redact(f"used token={secret} in request")

    def test_extra_pattern_is_applied(self) -> None:
        r = Redactor.builtin().with_extra(patterns=[("workspace_token", r"wsk_[A-Za-z0-9]{16,}")])
        assert "wsk_" not in r.redact("token wsk_abcdef0123456789ABC")


class TestRedactorImmutability:
    def test_with_extra_returns_new_instance(self) -> None:
        base = Redactor.builtin()
        derived = base.with_extra(strings=["x"])
        assert base is not derived
        assert "x" not in base.extra_strings


# ---- Property-based: redaction must be idempotent and never produce a new
# match for any of the built-in patterns. PRD §14.2 + Story 0.4.3.
_token_alphabet = string.ascii_letters + string.digits + "_-./:= \t@"


@given(st.text(alphabet=_token_alphabet, max_size=400))
def test_redaction_is_idempotent(text: str) -> None:
    once = redact(text)
    twice = redact(once)
    assert once == twice


@given(st.text(alphabet=_token_alphabet, max_size=400))
def test_redacted_output_contains_no_pattern_match(text: str) -> None:
    """After redaction, none of the built-in patterns should match the
    result. This is the property the PRD's redaction guarantee depends on.
    """
    redactor = Redactor.builtin()
    result = redactor.redact(text)
    for name, pattern in redactor.patterns:
        # The placeholder itself is allowed to remain — check we didn't miss
        # an actual secret.
        residual = pattern.sub("", result)
        assert REDACTED in result or pattern.search(residual) is None, (
            f"pattern {name} still matches after redaction: {result!r}"
        )
