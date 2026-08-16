from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.orchestration.services import AppServices

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/reviews/{review_id}")
async def review_events_ws(websocket: WebSocket, review_id: str) -> None:
    services: AppServices = websocket.app.state.services
    await websocket.accept()

    try:
        history = await services.event_bus.history(review_id)
        for event in history:
            await websocket.send_json(event.model_dump(mode="json"))

        queue = services.event_bus.subscribe(review_id)
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event.model_dump(mode="json"))
        finally:
            services.event_bus.unsubscribe(review_id, queue)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for review %s", review_id)
    except asyncio.CancelledError:
        raise
