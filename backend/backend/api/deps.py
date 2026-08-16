from __future__ import annotations

from fastapi import Request

from backend.core.orchestration.services import AppServices


def get_services(request: Request) -> AppServices:
    return request.app.state.services
