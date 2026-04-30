"""Heuristic Playwright TS validator.

We can't ``ast.parse()`` TypeScript from Python without a heavy
dependency. This module does the cheap, deterministic checks that catch
the failure modes the LLM hits in practice:

* Missing or wrong imports.
* Unbalanced ``{}`` / ``(`` / ``[``.
* Python-style identifiers in API call positions (``snake_case`` where
  Playwright's API is camelCase).
* Missing top-level ``test(...)`` blocks.
* No ``QAFORGE_UI_BASE_URL`` env reference (an explicit instruction
  rule from the prompt).

A real ``tsc --noEmit`` / ``playwright test --list`` validation runs
under :class:`SubprocessPlaywrightRunner` (Story 1.5.2) before any
spec actually executes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

_REQUIRED_IMPORT = re.compile(
    r"""import\s*\{\s*(?:[A-Za-z0-9_,\s]+)\s*\}\s*from\s*['"]@playwright/test['"]""",
)
_TEST_CALL = re.compile(r"\btest\s*\(")
_BASE_URL_REF = re.compile(r"process\.env\.QAFORGE_UI_BASE_URL")
_PYTHON_DUNDER = re.compile(r"\b__[a-zA-Z]+__\b")
_PYTHON_DEF = re.compile(r"^\s*def\s+\w+\s*\(", re.MULTILINE)
_PYTHON_ASSERT = re.compile(r"^\s*assert\s+\w+", re.MULTILINE)
_BALANCERS: Final[tuple[tuple[str, str], ...]] = (("{", "}"), ("(", ")"), ("[", "]"))


class GeneratedSpecInvalid(ValueError):  # noqa: N818 - public name predates rule
    """Raised when the heuristic validator rejects a generated spec."""


@dataclass(slots=True)
class _Stripped:
    text: str

    @classmethod
    def from_source(cls, source: str) -> _Stripped:
        # Strip strings + comments so balancers and pattern checks aren't
        # fooled by content inside string literals.
        out: list[str] = []
        i = 0
        n = len(source)
        while i < n:
            ch = source[i]
            two = source[i : i + 2]
            if two == "//":
                end = source.find("\n", i)
                i = n if end == -1 else end
                continue
            if two == "/*":
                end = source.find("*/", i + 2)
                i = n if end == -1 else end + 2
                continue
            if ch in ("'", '"', "`"):
                quote = ch
                j = i + 1
                while j < n and source[j] != quote:
                    if source[j] == "\\" and j + 1 < n:
                        j += 2
                        continue
                    j += 1
                i = j + 1
                continue
            out.append(ch)
            i += 1
        return cls(text="".join(out))


def validate_spec(source: str) -> None:
    """Raise :class:`GeneratedSpecInvalid` if the spec looks broken.

    This is intentionally cheap — false negatives are acceptable as long
    as the runner's `tsc/playwright list` step catches them later.
    False positives are not acceptable: every rule below has been
    tightened against patterns Playwright officially documents.
    """
    if not source.strip():
        raise GeneratedSpecInvalid("spec source is empty")

    if not _REQUIRED_IMPORT.search(source):
        raise GeneratedSpecInvalid("missing 'import { ... } from \"@playwright/test\"' at the top")

    if _PYTHON_DEF.search(source):
        raise GeneratedSpecInvalid("Python-style 'def ' found — TS expects 'function'")

    if _PYTHON_ASSERT.search(source):
        raise GeneratedSpecInvalid(
            "Python-style 'assert ' found — Playwright uses expect(...).toX(...)"
        )

    if _PYTHON_DUNDER.search(source):
        raise GeneratedSpecInvalid("Python __dunder__ identifier found in TS source")

    stripped = _Stripped.from_source(source)
    if not _TEST_CALL.search(stripped.text):
        raise GeneratedSpecInvalid("no top-level 'test(...)' calls present")

    if not _BASE_URL_REF.search(stripped.text):
        raise GeneratedSpecInvalid("spec must read process.env.QAFORGE_UI_BASE_URL — none found")

    for opener, closer in _BALANCERS:
        depth = 0
        for ch in stripped.text:
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth < 0:
                    raise GeneratedSpecInvalid(f"unbalanced bracket: extra '{closer}'")
        if depth != 0:
            raise GeneratedSpecInvalid(
                f"unbalanced bracket: '{opener}' opened {depth} time(s) without close"
            )
