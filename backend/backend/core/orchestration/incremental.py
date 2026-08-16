from __future__ import annotations

from backend.core.schemas.finding import Finding, IncrementalStatus
from backend.integrations.github.schemas import PRFile

# Architecture/Code Impact Agents build a real import/call graph "scoped to
# the diff" (see their docstrings) - on an incremental pass, that graph is
# built only from the delta files, so a smaller/different slice of the
# codebase than the finding was originally raised from. A prior finding
# from these two specifically that doesn't reappear can't be confidently
# called RESOLVED without the full multi-file context it depended on, so it
# gets INVALIDATED (needs a fresh look) instead of RESOLVED or STALE.
CROSS_FILE_AGENTS = {"architecture_agent", "code_impact_agent"}


def compute_delta(old_files: list[PRFile], new_files: list[PRFile]) -> list[PRFile]:
    """Real diff-of-diffs: a file counts as "changed since the last
    analyzed push" if it's new to the PR, or its patch text differs from
    what it was in the previous review. This - not a per-agent file-type
    registry - is what scopes an incremental run: `ctx.diff_files` is set
    to exactly this list, so every agent's existing `for pr_file in
    ctx.diff_files` loop naturally only analyzes what changed, with zero
    per-agent code changes needed."""
    old_by_name = {f.filename: f for f in old_files}
    delta: list[PRFile] = []
    for f in new_files:
        old = old_by_name.get(f.filename)
        if old is None or old.patch != f.patch:
            delta.append(f)
    return delta


def _line_key(f: Finding) -> tuple:
    return (f.file, f.line, f.category)


def _title_key(f: Finding) -> tuple:
    return (f.file, f.category, f.title)


def classify_findings(
    old_findings: list[Finding],
    new_findings: list[Finding],
    delta_filenames: set[str],
) -> dict[str, IncrementalStatus]:
    """Reconciles a previous review's findings against this incremental
    pass's fresh findings (which only ever came from re-analyzing
    `delta_filenames` - see compute_delta). Mutates `incremental_status` in
    place on both `old_findings` and `new_findings` and returns a
    finding-id -> status map for the INCREMENTAL_REVIEW_COMPLETED event.

    Rules (in order):
    - old finding's file wasn't touched this push -> STALE (carried
      forward untouched, not re-verified)
    - old finding's file WAS touched and a fresh finding matches it by
      (file, line, category) or (file, category, title) -> UNCHANGED (the
      responsible agent re-ran and found the same issue again)
    - old finding's file was touched, no match, but the detecting agent is
      a cross-file-graph agent -> INVALIDATED (see CROSS_FILE_AGENTS)
    - old finding's file was touched, no match, ordinary agent -> RESOLVED
      (the agent re-ran and the violation is genuinely gone)
    - any fresh finding with no old match -> NEW
    """
    by_line = {_line_key(f): f for f in new_findings if f.line is not None}
    by_title = {_title_key(f): f for f in new_findings}

    matched_new_ids: set[str] = set()
    statuses: dict[str, IncrementalStatus] = {}

    for old in old_findings:
        if old.file not in delta_filenames:
            old.incremental_status = IncrementalStatus.STALE
            statuses[old.id] = IncrementalStatus.STALE
            continue

        match = by_line.get(_line_key(old)) or by_title.get(_title_key(old))
        if match is not None:
            match.incremental_status = IncrementalStatus.UNCHANGED
            matched_new_ids.add(match.id)
            statuses[old.id] = IncrementalStatus.UNCHANGED
            continue

        if old.detecting_agent in CROSS_FILE_AGENTS:
            old.incremental_status = IncrementalStatus.INVALIDATED
            statuses[old.id] = IncrementalStatus.INVALIDATED
        else:
            statuses[old.id] = IncrementalStatus.RESOLVED

    for f in new_findings:
        if f.id not in matched_new_ids and f.incremental_status is None:
            f.incremental_status = IncrementalStatus.NEW
            statuses[f.id] = IncrementalStatus.NEW

    return statuses
