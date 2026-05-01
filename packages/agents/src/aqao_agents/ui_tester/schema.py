"""Output schema for the UI Testing Agent."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GeneratedUiTest(BaseModel):
    """One Playwright ``test(...)`` block plus what it covers."""

    model_config = ConfigDict(extra="forbid")

    test_case_title: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    journey_steps: list[str] = Field(default_factory=list)
    expected_outcome: str = Field(min_length=1)
    requires_auth: bool = True


class GeneratedUiTestSpec(BaseModel):
    """A single Playwright spec file containing the generated tests."""

    model_config = ConfigDict(extra="forbid")

    framework: str = Field(default="@playwright/test")
    spec_filename: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[a-z][a-z0-9_-]*\.spec\.ts$",
    )
    source_code: str = Field(min_length=1, max_length=200_000)
    tests: list[GeneratedUiTest] = Field(min_length=1)
