from __future__ import annotations

import logging

from backend.config.settings import Settings
from backend.integrations.tracing.client_protocol import TracingClient
from backend.integrations.tracing.composite_client import CompositeTracingClient
from backend.integrations.tracing.noop_client import NoOpTracingClient

logger = logging.getLogger(__name__)


def build_tracing_client(settings: Settings) -> CompositeTracingClient:
    """Returns a CompositeTracingClient fanning out to every tracing backend
    that's both configured (env vars set) and importable (SDK installed).
    Zero configured backends -> a single NoOpTracingClient, so GraphEngine
    always has exactly one TracingClient to call regardless of setup."""
    clients: list[TracingClient] = []

    if settings.langfuse_public_key and settings.langfuse_secret_key:
        from backend.integrations.tracing.langfuse_client import (
            LangfuseTracingClient,
            is_langfuse_available,
        )

        if is_langfuse_available():
            logger.info(
                "Using LangfuseTracingClient (host=%s)", settings.langfuse_host or "cloud default"
            )
            clients.append(
                LangfuseTracingClient(
                    settings.langfuse_public_key,
                    settings.langfuse_secret_key,
                    settings.langfuse_host,
                )
            )
        else:
            logger.warning(
                "[MOCK] LANGFUSE_* keys set but the `langfuse` package isn't installed - skipping"
            )

    if settings.langsmith_api_key:
        from backend.integrations.tracing.langsmith_client import (
            LangSmithTracingClient,
            is_langsmith_available,
        )

        if is_langsmith_available():
            logger.info("Using LangSmithTracingClient (project=%s)", settings.langsmith_project)
            clients.append(
                LangSmithTracingClient(settings.langsmith_api_key, settings.langsmith_project)
            )
        else:
            logger.warning(
                "[MOCK] LANGSMITH_API_KEY set but the `langsmith` package isn't installed - skipping"
            )

    if not clients:
        logger.info("[MOCK] No tracing backend configured - using NoOpTracingClient")
        clients.append(NoOpTracingClient())

    return CompositeTracingClient(clients)
