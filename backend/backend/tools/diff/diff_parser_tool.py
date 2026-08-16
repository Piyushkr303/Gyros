from __future__ import annotations

from typing import Any

from unidiff import PatchSet

from backend.tools.base import Tool


class DiffParserTool(Tool):
    """Parses a unified diff patch string into structured hunks (added/removed
    line numbers per file) so agents can cite exact file:line evidence
    without needing the whole repository."""

    name = "diff_parser"
    description = "Parse a unified diff patch into structured added/removed line ranges."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        filename: str = input["filename"]
        patch: str = input.get("patch") or ""
        if not patch:
            return {"filename": filename, "hunks": [], "added_lines": [], "removed_lines": []}

        # unidiff expects a full multi-file diff header; wrap a single-file patch.
        wrapped = f"--- a/{filename}\n+++ b/{filename}\n{patch}"
        patch_set = PatchSet(wrapped)

        hunks: list[dict] = []
        added_lines: list[int] = []
        removed_lines: list[int] = []
        added_line_texts: list[dict] = []
        for patched_file in patch_set:
            for hunk in patched_file:
                hunk_added = [
                    line.target_line_no for line in hunk if line.is_added and line.target_line_no
                ]
                hunk_removed = [
                    line.source_line_no for line in hunk if line.is_removed and line.source_line_no
                ]
                added_lines.extend(hunk_added)
                removed_lines.extend(hunk_removed)
                for line in hunk:
                    if line.is_added and line.target_line_no:
                        added_line_texts.append(
                            {"lineno": line.target_line_no, "text": line.value.rstrip("\n")}
                        )
                hunks.append(
                    {
                        "source_start": hunk.source_start,
                        "source_length": hunk.source_length,
                        "target_start": hunk.target_start,
                        "target_length": hunk.target_length,
                        "added_lines": hunk_added,
                        "removed_lines": hunk_removed,
                    }
                )

        return {
            "filename": filename,
            "hunks": hunks,
            "added_lines": added_lines,
            "removed_lines": removed_lines,
            "added_line_texts": added_line_texts,
        }
