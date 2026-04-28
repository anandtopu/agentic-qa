"""Pattern-based secret redaction.

Patterns target the credential shapes most likely to leak from agent tool
calls: API keys for LLM providers, GitHub PATs, JWTs, basic-auth headers,
private keys, AWS credentials, and generic high-entropy bearer tokens.

Workspaces can register additional patterns at runtime; see
`Redactor.with_extra`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

REDACTED = "[REDACTED]"

# Order matters: more specific patterns first so generic high-entropy
# patterns don't swallow them.
_BUILTIN_PATTERNS: tuple[tuple[str, str], ...] = (
    ("anthropic_key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("openai_key", r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    ("google_api_key", r"AIza[0-9A-Za-z_\-]{35}"),
    ("github_pat", r"gh[posu]_[A-Za-z0-9]{36,}"),
    ("aws_access_key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("aws_secret_key", r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?"),
    ("private_key_block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    ("jwt", r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    ("authorization_bearer", r"(?i)\b(authorization\s*[:=]\s*bearer)\s+[A-Za-z0-9._\-+/=]+"),
    ("basic_auth_header", r"(?i)\b(authorization\s*[:=]\s*basic)\s+[A-Za-z0-9+/=]+"),
    ("password_kv", r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?[^\s'\"]{4,}['\"]?"),
    ("url_userinfo", r"\b([a-z][a-z0-9+\-.]*://)[^\s/@]+:[^\s/@]+@"),
)


@dataclass(frozen=True)
class Redactor:
    """Compiled redaction engine. Immutable; combine via `with_extra`."""

    patterns: tuple[tuple[str, re.Pattern[str]], ...]
    placeholder: str = REDACTED
    extra_strings: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def builtin(cls) -> Redactor:
        compiled = tuple((name, re.compile(pat)) for name, pat in _BUILTIN_PATTERNS)
        return cls(patterns=compiled)

    def with_extra(
        self,
        *,
        patterns: Iterable[tuple[str, str]] = (),
        strings: Iterable[str] = (),
    ) -> Redactor:
        """Return a new Redactor with extra patterns and exact-string secrets.

        Use `strings` for known sensitive values (e.g. an injected API key
        loaded from config) so the redactor can scrub them even when they
        don't match a generic pattern.
        """
        compiled = tuple((name, re.compile(pat)) for name, pat in patterns)
        new_strings = frozenset(s for s in strings if s)
        return Redactor(
            patterns=self.patterns + compiled,
            placeholder=self.placeholder,
            extra_strings=self.extra_strings | new_strings,
        )

    def redact(self, text: str) -> str:
        if not text:
            return text
        out = text
        # Pattern-based replacement.
        for name, pattern in self.patterns:
            out = pattern.sub(self._replacement_for(name), out)
        # Exact-string replacement (after patterns to avoid partial overlaps).
        for secret in self.extra_strings:
            if secret in out:
                out = out.replace(secret, self.placeholder)
        return out

    def _replacement_for(self, name: str) -> str:
        # Some patterns capture a leading group (header name, scheme) that
        # we want to preserve. Convention: if a pattern has a group named or
        # anonymous group 1, preserve it; otherwise replace the whole match.
        if name in {"authorization_bearer", "basic_auth_header"}:
            return rf"\1 {self.placeholder}"
        if name == "url_userinfo":
            return rf"\1{self.placeholder}@"
        if name == "password_kv":
            return rf"\1={self.placeholder}"
        return self.placeholder


_default = Redactor.builtin()


def default_redactor() -> Redactor:
    """Process-wide default redactor (built-in patterns only)."""
    return _default


def redact(text: str) -> str:
    """Convenience: redact with built-in patterns."""
    return _default.redact(text)
