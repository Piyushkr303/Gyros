from pathlib import Path

from backend.integrations.jira.mock_client import MockJiraClient

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "demo_pr"


async def test_search_issues_matches_fixture_by_keyword():
    client = MockJiraClient(FIXTURES_DIR)
    issue = await client.get_issue("JIRA-142")
    assert issue is not None

    hits = await client.search_issues(issue.summary.split()[0])
    assert hits == [issue]

    assert await client.search_issues("no-such-keyword-xyz") == []


async def test_add_comment_and_transition_status_round_trip():
    client = MockJiraClient(FIXTURES_DIR)

    assert await client.add_comment("JIRA-142", "Review published.") is True
    assert await client.add_comment("UNKNOWN-1", "no-op") is False

    assert await client.transition_status("JIRA-142", "In Review") is True
    updated = await client.get_issue("JIRA-142")
    assert updated is not None
    assert updated.status == "In Review"

    assert await client.transition_status("UNKNOWN-1", "Done") is False
