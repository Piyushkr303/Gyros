from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from backend.core.events.event_bus import EventBus
from backend.core.persistence.repositories import AgentMessageRepository
from backend.core.schemas.events import EventType
from backend.core.schemas.message import AgentMessage, MessageType
from backend.core.utils import new_id, now_iso

logger = logging.getLogger(__name__)


class MessageBus:
    """Structured agent-to-agent communication (spec §38). Messages carry
    references (finding_id, evidence_ids), never raw context blobs."""

    def __init__(self, event_bus: EventBus, message_repository: AgentMessageRepository) -> None:
        self._event_bus = event_bus
        self._repo = message_repository
        self._inboxes: dict[str, asyncio.Queue[AgentMessage]] = defaultdict(asyncio.Queue)
        self._by_review: dict[str, list[AgentMessage]] = defaultdict(list)

    async def send(
        self,
        *,
        review_id: str,
        sender: str,
        receiver: str,
        type: MessageType,
        summary: str,
        finding_id: str | None = None,
        evidence_ids: list[str] | None = None,
        confidence: float | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            message_id=new_id("M"),
            review_id=review_id,
            sender=sender,
            receiver=receiver,
            type=type,
            finding_id=finding_id,
            summary=summary,
            evidence_ids=evidence_ids or [],
            confidence=confidence,
            timestamp=now_iso(),
        )
        self._by_review[review_id].append(message)
        self._inboxes[f"{review_id}:{receiver}"].put_nowait(message)

        try:
            await self._repo.add(message)
        except Exception:  # pragma: no cover
            logger.exception("Failed to persist message %s", message.message_id)

        await self._event_bus.publish(
            review_id,
            EventType.AGENT_MESSAGE_SENT,
            {"message": message.model_dump(mode="json")},
        )
        await self._event_bus.publish(
            review_id,
            EventType.AGENT_MESSAGE_RECEIVED,
            {"message": message.model_dump(mode="json")},
        )
        return message

    def inbox(self, review_id: str, agent_name: str) -> asyncio.Queue[AgentMessage]:
        return self._inboxes[f"{review_id}:{agent_name}"]

    def history(self, review_id: str) -> list[AgentMessage]:
        return list(self._by_review.get(review_id, []))
