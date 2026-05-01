"""Playwright runner — Story 1.5.2.

Production runner shells out to ``npx playwright test``. The Stub mirrors
the same interface for unit tests (no node, no browsers) and is used
end-to-end across the integration suite until a real Playwright image
is wired in.
"""

from aqao_tools.playwright_runner.runner import (
    PlaywrightArtifact,
    PlaywrightResult,
    PlaywrightRunner,
    PlaywrightRunnerError,
    PlaywrightTestOutcome,
    PlaywrightTestResult,
    StubPlaywrightRunner,
)

__all__ = [
    "PlaywrightArtifact",
    "PlaywrightResult",
    "PlaywrightRunner",
    "PlaywrightRunnerError",
    "PlaywrightTestOutcome",
    "PlaywrightTestResult",
    "StubPlaywrightRunner",
]
