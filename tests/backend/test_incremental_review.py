from pathlib import Path

from backend.core.orchestration.incremental import classify_findings, compute_delta
from backend.core.schemas.finding import CriticStatus, Finding, IncrementalStatus, Severity, ValidationStatus
from backend.core.utils import new_id, now_iso
from backend.integrations.github.mock_client import MockGitHubClient
from backend.integrations.github.schemas import PRFile

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "demo_pr"


def _finding(**overrides) -> Finding:
    now = now_iso()
    base = dict(
        id=new_id("F"),
        review_id="rev-old",
        severity=Severity.HIGH,
        category="security",
        file="payment_service.py",
        line=24,
        title="Missing authorization check",
        description="...",
        detecting_agent="security_agent",
        validator_status=ValidationStatus.CONFIRMED,
        critic_status=CriticStatus.ACCEPTED,
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return Finding(**base)


def test_compute_delta_flags_new_and_changed_files_only():
    old = [PRFile(filename="a.py", status="modified", patch="patch-a-v1"), PRFile(filename="b.py", status="modified", patch="patch-b")]
    new = [
        PRFile(filename="a.py", status="modified", patch="patch-a-v2"),  # changed
        PRFile(filename="b.py", status="modified", patch="patch-b"),  # unchanged
        PRFile(filename="c.py", status="added", patch="patch-c"),  # new
    ]

    delta = compute_delta(old, new)

    assert {f.filename for f in delta} == {"a.py", "c.py"}


def test_classify_findings_resolved_when_file_touched_and_no_match():
    old = [_finding()]
    statuses = classify_findings(old, new_findings=[], delta_filenames={"payment_service.py"})

    assert statuses[old[0].id] == IncrementalStatus.RESOLVED


def test_classify_findings_unchanged_when_same_line_and_category_recur():
    old_finding = _finding()
    new_finding = _finding(id=new_id("F"), review_id="rev-new")

    statuses = classify_findings([old_finding], [new_finding], delta_filenames={"payment_service.py"})

    assert statuses[old_finding.id] == IncrementalStatus.UNCHANGED
    assert new_finding.incremental_status == IncrementalStatus.UNCHANGED


def test_classify_findings_stale_when_file_not_in_delta():
    old_finding = _finding(file="add_promo_code_migration.sql", line=None, category="database")

    statuses = classify_findings([old_finding], [], delta_filenames={"payment_service.py"})

    assert statuses[old_finding.id] == IncrementalStatus.STALE
    assert old_finding.incremental_status == IncrementalStatus.STALE


def test_classify_findings_invalidated_for_cross_file_agents_without_a_match():
    old_finding = _finding(detecting_agent="architecture_agent", category="architecture")

    statuses = classify_findings([old_finding], [], delta_filenames={"payment_service.py"})

    assert statuses[old_finding.id] == IncrementalStatus.INVALIDATED


def test_classify_findings_new_for_unmatched_fresh_finding():
    fresh = _finding(id=new_id("F"), review_id="rev-new", file="requirements.txt", line=6, category="dependency")

    statuses = classify_findings(old_findings=[], new_findings=[fresh], delta_filenames={"requirements.txt"})

    assert statuses[fresh.id] == IncrementalStatus.NEW
    assert fresh.incremental_status == IncrementalStatus.NEW


async def test_mock_github_client_serves_a_followup_revision():
    client = MockGitHubClient(FIXTURES_DIR)
    assert client.has_followup_revision()

    first = await client.get_pull_request("demo-org/demo-payments", 238)
    assert {f.filename for f in first.files} == {
        "payment_service.py",
        "requirements.txt",
        "add_promo_code_migration.sql",
        "frontend/src/components/PromoBanner.tsx",
    }

    client.advance_revision()
    followup = await client.get_pull_request("demo-org/demo-payments", 238)
    assert followup.head_sha != first.head_sha

    delta = compute_delta(first.files, followup.files)
    # payment_service.py and requirements.txt changed further; the SQL
    # migration and the frontend banner file didn't, so they must NOT
    # appear in the delta even though they're still part of the PR.
    assert {f.filename for f in delta} == {"payment_service.py", "requirements.txt"}
