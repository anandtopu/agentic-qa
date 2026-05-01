"""Agentic QA Orchestrator execution-plane tools (Phase 1).

* :mod:`aqao_tools.credentials` — credential broker that bridges the
  Control Plane's per-environment variables (Story 1.1.3) into tool runs
  while registering each value with the redactor.
* :mod:`aqao_tools.newman` — Postman/Newman runner.
* :mod:`aqao_tools.pytest_runner` — pytest+httpx runner.

Each module is structured so production callers depend on a Protocol
and tests inject a stub.
"""

from aqao_tools.credentials import (
    CredentialBroker,
    InMemoryCredentialBroker,
    SecretBundle,
)
from aqao_tools.newman import (
    NewmanAssertion,
    NewmanResult,
    NewmanRunner,
    NewmanRunnerError,
    StubNewmanRunner,
)
from aqao_tools.playwright_runner import (
    PlaywrightArtifact,
    PlaywrightResult,
    PlaywrightRunner,
    PlaywrightRunnerError,
    PlaywrightTestOutcome,
    PlaywrightTestResult,
    StubPlaywrightRunner,
)
from aqao_tools.pytest_runner import (
    PytestResult,
    PytestRunner,
    PytestRunnerError,
    StubPytestRunner,
    TestOutcome,
)
from aqao_tools.router import (
    ToolBudgetExceeded,
    ToolCallable,
    ToolDescriptor,
    ToolNotFoundError,
    ToolRouter,
)

__all__ = [
    "CredentialBroker",
    "InMemoryCredentialBroker",
    "NewmanAssertion",
    "NewmanResult",
    "NewmanRunner",
    "NewmanRunnerError",
    "PlaywrightArtifact",
    "PlaywrightResult",
    "PlaywrightRunner",
    "PlaywrightRunnerError",
    "PlaywrightTestOutcome",
    "PlaywrightTestResult",
    "PytestResult",
    "PytestRunner",
    "PytestRunnerError",
    "SecretBundle",
    "StubNewmanRunner",
    "StubPlaywrightRunner",
    "StubPytestRunner",
    "TestOutcome",
    "ToolBudgetExceeded",
    "ToolCallable",
    "ToolDescriptor",
    "ToolNotFoundError",
    "ToolRouter",
]
