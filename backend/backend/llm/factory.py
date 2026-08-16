from __future__ import annotations

import logging

from backend.config.settings import Settings
from backend.llm.base.provider import LLMProvider
from backend.llm.groq.mock_provider import MockGroqProvider
from backend.llm.groq.real_provider import RealGroqProvider

logger = logging.getLogger(__name__)


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.groq_api_key:
        logger.info("Using RealGroqProvider (model=%s)", settings.groq_model)
        return RealGroqProvider(api_key=settings.groq_api_key, model=settings.groq_model)
    logger.warning("[MOCK] GROQ_API_KEY not set - using MockGroqProvider")
    return MockGroqProvider()
