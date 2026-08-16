from __future__ import annotations

import logging

from backend.config.settings import Settings
from backend.integrations.jira.client_protocol import JiraClient
from backend.integrations.jira.mock_client import MockJiraClient
from backend.integrations.jira.real_client import RealJiraClient

logger = logging.getLogger(__name__)


def build_jira_client(settings: Settings) -> JiraClient:
    if settings.jira_base_url and settings.jira_api_token:
        logger.info("Using RealJiraClient")
        return RealJiraClient(
            base_url=settings.jira_base_url,
            email=settings.jira_email,
            api_token=settings.jira_api_token,
        )
    logger.warning(
        "[MOCK] JIRA_BASE_URL/JIRA_API_TOKEN not set - using MockJiraClient (tests/fixtures/demo_pr)"
    )
    return MockJiraClient(fixtures_dir=settings.fixtures_dir)
