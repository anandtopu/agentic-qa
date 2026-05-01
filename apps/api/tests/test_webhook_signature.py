"""Unit tests for GitHub webhook signature verification — Story 1.2.1."""

from __future__ import annotations

import hashlib
import hmac

from aqao_api.webhooks.github import verify_signature


def _signed(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_valid_signature_passes() -> None:
    body = b'{"action":"opened"}'
    assert verify_signature(secret="topsecret", body=body, header_value=_signed(body, "topsecret"))


def test_wrong_secret_fails() -> None:
    body = b'{"action":"opened"}'
    assert not verify_signature(
        secret="topsecret",
        body=body,
        header_value=_signed(body, "different-secret"),
    )


def test_tampered_body_fails() -> None:
    secret = "topsecret"
    sig = _signed(b'{"action":"opened"}', secret)
    assert not verify_signature(
        secret=secret,
        body=b'{"action":"closed"}',
        header_value=sig,
    )


def test_missing_header_fails() -> None:
    assert not verify_signature(secret="x", body=b"{}", header_value=None)


def test_wrong_prefix_fails() -> None:
    body = b"{}"
    digest = hmac.new(b"x", body, digestmod=hashlib.sha256).hexdigest()
    assert not verify_signature(secret="x", body=body, header_value=f"sha1={digest}")


def test_empty_secret_fails_safely() -> None:
    assert not verify_signature(secret="", body=b"{}", header_value="sha256=anything")
