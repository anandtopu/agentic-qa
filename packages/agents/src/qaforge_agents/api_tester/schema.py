"""Output schema for the API Testing Agent."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GeneratedTest(BaseModel):
    """One generated pytest function plus what it covers."""

    model_config = ConfigDict(extra="forbid")

    test_case_title: str = Field(min_length=1, max_length=500)
    function_name: str = Field(min_length=1, max_length=200, pattern=r"^test_[a-zA-Z0-9_]+$")
    method: str = Field(pattern=r"^(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$")
    path: str = Field(min_length=1, max_length=500)
    expected_status: int = Field(ge=100, le=599)
    is_negative: bool = False
    requires_auth: bool = True


class GeneratedTestSuite(BaseModel):
    """Single source file containing the generated tests + metadata."""

    model_config = ConfigDict(extra="forbid")

    framework: str = Field(default="pytest+httpx")
    module_name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    source_code: str = Field(min_length=1, max_length=200_000)
    tests: list[GeneratedTest] = Field(min_length=1)
