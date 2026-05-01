"""UsageQueryService — Story 2.5.2."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aqao_api.db.models import UsageRecordRow


@dataclass(slots=True)
class UsageBucket:
    label: str
    usd_cost: Decimal
    prompt_tokens: int
    completion_tokens: int
    call_count: int


@dataclass(slots=True)
class UsageSummary:
    total_usd_cost: Decimal
    total_prompt_tokens: int
    total_completion_tokens: int
    total_calls: int
    by_agent: list[UsageBucket]
    by_provider: list[UsageBucket]
    since: datetime | None
    until: datetime | None


class UsageQueryService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def summary(
        self,
        *,
        workspace_id: UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> UsageSummary:
        base_filters = []
        if workspace_id is not None:
            base_filters.append(UsageRecordRow.workspace_id == workspace_id)
        if since is not None:
            base_filters.append(UsageRecordRow.created_at >= since)
        if until is not None:
            base_filters.append(UsageRecordRow.created_at < until)

        totals_stmt = select(
            func.coalesce(func.sum(UsageRecordRow.usd_cost), 0),
            func.coalesce(func.sum(UsageRecordRow.prompt_tokens), 0),
            func.coalesce(func.sum(UsageRecordRow.completion_tokens), 0),
            func.count(UsageRecordRow.id),
        )
        for f in base_filters:
            totals_stmt = totals_stmt.where(f)
        total_usd, total_prompt, total_completion, total_calls = self._session.execute(
            totals_stmt
        ).one()

        by_agent = self._group_by(UsageRecordRow.agent_name, base_filters)
        by_provider = self._group_by(UsageRecordRow.provider, base_filters)

        return UsageSummary(
            total_usd_cost=Decimal(total_usd),
            total_prompt_tokens=int(total_prompt),
            total_completion_tokens=int(total_completion),
            total_calls=int(total_calls),
            by_agent=by_agent,
            by_provider=by_provider,
            since=since,
            until=until,
        )

    def _group_by(  # type: ignore[no-untyped-def]
        self, column, filters: Sequence[Any]
    ) -> list[UsageBucket]:
        stmt = (
            select(
                column.label("bucket"),
                func.sum(UsageRecordRow.usd_cost),
                func.sum(UsageRecordRow.prompt_tokens),
                func.sum(UsageRecordRow.completion_tokens),
                func.count(UsageRecordRow.id),
            )
            .group_by(column)
            .order_by(func.sum(UsageRecordRow.usd_cost).desc())
        )
        for f in filters:
            stmt = stmt.where(f)
        rows = self._session.execute(stmt).all()
        return [
            UsageBucket(
                label=str(row[0]),
                usd_cost=Decimal(row[1]),
                prompt_tokens=int(row[2]),
                completion_tokens=int(row[3]),
                call_count=int(row[4]),
            )
            for row in rows
        ]
