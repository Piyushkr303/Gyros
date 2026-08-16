from __future__ import annotations

import logging

from backend.config.settings import Settings
from backend.integrations.github.client_protocol import GitHubClient
from backend.integrations.github.mock_client import MockGitHubClient
from backend.integrations.github.real_client import RealGitHubClient

logger = logging.getLogger(__name__)


def build_github_client(settings: Settings) -> GitHubClient:
    if settings.github_token:
        logger.info("Using RealGitHubClient")
        return RealGitHubClient(token=settings.github_token)
    logger.warning("[MOCK] GITHUB_TOKEN not set - using MockGitHubClient (tests/fixtures/demo_pr)")
    return MockGitHubClient(fixtures_dir=settings.fixtures_dir)
