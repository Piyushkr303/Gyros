from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum


class ApprovalAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EDIT = "EDIT"


@dataclass
class ApprovalDecision:
    action: ApprovalAction
    edited_body: str | None = None
    decided_by: str = "human"


class HumanApprovalGate:
    """Blocks graph execution until a human resolves the pending review via the API (spec §77)."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[ApprovalDecision]] = {}

    def open(self, review_id: str) -> None:
        loop = asyncio.get_event_loop()
        self._pending[review_id] = loop.create_future()

    async def wait_for_decision(self, review_id: str) -> ApprovalDecision:
        if review_id not in self._pending:
            self.open(review_id)
        return await self._pending[review_id]

    def resolve(self, review_id: str, decision: ApprovalDecision) -> bool:
        future = self._pending.get(review_id)
        if future is None or future.done():
            return False
        future.set_result(decision)
        return True

    def is_pending(self, review_id: str) -> bool:
        future = self._pending.get(review_id)
        return future is not None and not future.done()
