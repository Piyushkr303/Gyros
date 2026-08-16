from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator

from backend.core.persistence.repositories import EventRepository
from backend.core.schemas.events import Event, EventType
from backend.core.utils import new_id, now_iso

logger = logging.getLogger(__name__)


class EventBus:
    """Central pub/sub for review execution events.

    Every event is persisted (so a late WebSocket subscriber or a restarted
    backend can replay history) and fanned out to live per-review subscriber
    queues for real-time streaming.
    """

    def __init__(self, event_repository: EventRepository) -> None:
        self._repo = event_repository
        self._subscribers: dict[str, set[asyncio.Queue[Event]]] = defaultdict(set)
        self._memory_history: dict[str, list[Event]] = defaultdict(list)

    async def publish(self, review_id: str, type: EventType, payload: dict | None = None) -> Event:
        event = Event(
            id=new_id("evt"),
            type=type,
            review_id=review_id,
            timestamp=now_iso(),
            payload=payload or {},
        )
        self._memory_history[review_id].append(event)
        try:
            await self._repo.add(event)
        except Exception:  # pragma: no cover - persistence must never break execution
            logger.exception("Failed to persist event %s", event.id)

        for queue in list(self._subscribers.get(review_id, set())):
            queue.put_nowait(event)

        return event

    def subscribe(self, review_id: str) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers[review_id].add(queue)
        return queue

    def unsubscribe(self, review_id: str, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.get(review_id, set()).discard(queue)

    async def history(self, review_id: str) -> list[Event]:
        if review_id in self._memory_history:
            return list(self._memory_history[review_id])
        events = await self._repo.list_by_review(review_id)
        self._memory_history[review_id] = list(events)
        return events

    async def stream(self, review_id: str) -> AsyncIterator[Event]:
        queue = self.subscribe(review_id)
        try:
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe(review_id, queue)
