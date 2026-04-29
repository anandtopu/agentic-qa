"""LLMClient — the single interface every agent uses to call a model.

Responsibilities (ADR-0004):

* Resolve a ``Tier`` to an ordered list of (provider, model) candidates.
* Run the call through the chosen adapter.
* Compute USD cost from the pricing table and emit a ``UsageRecord``.
* Validate structured outputs against an optional Pydantic schema.
* Retry transient failures and fail over to the next candidate.
* Never log raw provider payloads — redaction wraps every text sink.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

import structlog
from pydantic import BaseModel, ValidationError

from qaforge_agents.llm.pricing import PricingTable, default_pricing
from qaforge_agents.llm.providers.base import Provider, ProviderError, ProviderResponse
from qaforge_agents.llm.recorder import InMemoryRecorder, UsageRecorder
from qaforge_agents.llm.types import (
    LLMRequest,
    LLMResponse,
    ModelSpec,
    Tier,
    UsageRecord,
)

_DEFAULT_TIER_MODELS: dict[Tier, list[ModelSpec]] = {
    Tier.HIGH: [
        ModelSpec(provider="anthropic", model="claude-opus-4-7"),
        ModelSpec(provider="anthropic", model="claude-sonnet-4-6"),
    ],
    Tier.MID: [
        ModelSpec(provider="anthropic", model="claude-sonnet-4-6"),
        ModelSpec(provider="openai", model="gpt-5.1"),
    ],
    Tier.LOW: [
        ModelSpec(provider="anthropic", model="claude-haiku-4-5"),
        ModelSpec(provider="openai", model="gpt-5.1-mini"),
    ],
}


class StructuredOutputError(ValueError):
    """Raised when an LLM response doesn't match the requested schema."""


class LLMClient:
    """Provider-neutral entry point for every LLM call in the platform."""

    def __init__(
        self,
        *,
        providers: dict[str, Provider],
        recorder: UsageRecorder | None = None,
        pricing: PricingTable | None = None,
        tier_models: dict[Tier, list[ModelSpec]] | None = None,
        max_attempts_per_candidate: int = 2,
    ) -> None:
        self._providers = providers
        self._recorder: UsageRecorder = recorder or InMemoryRecorder()
        self._pricing = pricing or default_pricing()
        self._tier_models = tier_models or _DEFAULT_TIER_MODELS
        self._max_attempts = max_attempts_per_candidate
        self._log = structlog.get_logger("qaforge_agents.llm.client")

    @property
    def recorder(self) -> UsageRecorder:
        return self._recorder

    async def complete(self, request: LLMRequest) -> LLMResponse:
        candidates = self._candidates_for(request.tier)
        last_error: ProviderError | None = None

        for spec in candidates:
            provider = self._providers.get(spec.provider)
            if provider is None:
                continue
            try:
                return await self._run(provider, spec, request)
            except ProviderError as err:
                last_error = err
                self._log.warning(
                    "llm.provider_failed",
                    provider=spec.provider,
                    model=spec.model,
                    transient=err.transient,
                    correlation_id=request.correlation_id,
                )
                if not err.transient:
                    continue  # try next candidate
                continue

        if last_error is not None:
            raise last_error
        raise ProviderError("client", f"no provider available for tier {request.tier}")

    async def _run(self, provider: Provider, spec: ModelSpec, request: LLMRequest) -> LLMResponse:
        attempts = 0
        last_transient: ProviderError | None = None

        while attempts < self._max_attempts:
            attempts += 1
            started = UsageRecord.now_utc()
            t0 = time.monotonic()
            try:
                provider_response = await provider.complete(
                    model=spec.model,
                    messages=request.messages,
                    max_output_tokens=request.max_output_tokens,
                    temperature=request.temperature,
                )
            except ProviderError as err:
                if err.transient and attempts < self._max_attempts:
                    last_transient = err
                    continue
                raise

            finished = UsageRecord.now_utc()
            latency_ms = int((time.monotonic() - t0) * 1000)
            usage = self._build_usage(
                spec=spec,
                request=request,
                response=provider_response,
                started=started,
                finished=finished,
                latency_ms=latency_ms,
            )
            self._recorder.record(usage)

            structured = self._validate_structured(provider_response.content, request)
            return LLMResponse(
                content=provider_response.content,
                structured=structured,
                usage=usage,
            )

        # Exhausted retries on the same candidate; let the caller try the next.
        assert last_transient is not None
        raise last_transient

    def _candidates_for(self, tier: Tier) -> Iterable[ModelSpec]:
        return self._tier_models.get(tier, self._tier_models[Tier.MID])

    def _build_usage(
        self,
        *,
        spec: ModelSpec,
        request: LLMRequest,
        response: ProviderResponse,
        started: datetime,
        finished: datetime,
        latency_ms: int,
    ) -> UsageRecord:
        pricing = self._pricing.get((spec.provider, spec.model))
        if pricing is None:
            self._log.warning(
                "llm.pricing_missing",
                provider=spec.provider,
                model=spec.model,
            )
            usd_cost = Decimal("0")
        else:
            usd_cost = pricing.cost_for(
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                cached_prompt_tokens=response.cached_prompt_tokens,
            )

        return UsageRecord(
            provider=spec.provider,
            model=spec.model,
            tier=request.tier,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            cached_prompt_tokens=response.cached_prompt_tokens,
            usd_cost=usd_cost,
            latency_ms=latency_ms,
            correlation_id=request.correlation_id,
            workspace_id=request.workspace_id,
            started_at=started,
            finished_at=finished,
            metadata=dict(request.metadata),
        )

    @staticmethod
    def _validate_structured(content: str, request: LLMRequest) -> BaseModel | None:
        if request.response_schema is None:
            return None
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise StructuredOutputError(f"response is not valid JSON: {exc.msg}") from exc
        try:
            return request.response_schema.model_validate(payload)
        except ValidationError as exc:
            raise StructuredOutputError(
                f"response failed schema validation: {exc.errors(include_url=False)}"
            ) from exc
