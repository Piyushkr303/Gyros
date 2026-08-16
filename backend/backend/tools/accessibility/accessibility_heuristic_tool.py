from __future__ import annotations

import re
from typing import Any

from backend.tools.base import Tool

# Regex-based, not a JSX/TSX parser (Python has no built-in one) - mirrors
# the same real+fallback pragmatism as RegexHeuristicTool for cross-language
# checks that stdlib `ast` can't reach.
_IMG_NO_ALT = re.compile(r"<img(?![^>]*\balt\s*=)[^>]*/?>", re.IGNORECASE)
_CLICKABLE_DIV_NO_ROLE = re.compile(
    r"<(div|span)(?=[^>]*\bonClick\s*=)(?![^>]*\brole\s*=)(?![^>]*\btabIndex\s*=)[^>]*>",
    re.IGNORECASE,
)


class AccessibilityHeuristicTool(Tool):
    """Regex heuristics over JSX/TSX/HTML source: <img> tags with no `alt`
    attribute, and onClick-bearing <div>/<span> elements with no `role` or
    `tabIndex` (not keyboard- or screen-reader-accessible)."""

    name = "accessibility_heuristics"
    description = (
        "Detect missing alt text and non-semantic clickable elements in JSX/TSX/HTML source."
    )

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        source: str = input.get("source") or ""
        if not source:
            return {"accessibility_findings": []}

        findings: list[dict] = []
        lines = source.splitlines()
        for i, line in enumerate(lines, start=1):
            if _IMG_NO_ALT.search(line):
                findings.append(
                    {
                        "lineno": i,
                        "type": "img_missing_alt",
                        "message": f"Line {i}: <img> has no `alt` attribute, inaccessible to screen readers.",
                    }
                )
            if _CLICKABLE_DIV_NO_ROLE.search(line):
                findings.append(
                    {
                        "lineno": i,
                        "type": "non_semantic_clickable",
                        "message": (
                            f"Line {i}: onClick on a <div>/<span> with no `role` or `tabIndex` is not "
                            "keyboard-operable or screen-reader-exposed; use a <button> or add role+tabIndex+onKeyDown."
                        ),
                    }
                )

        return {"accessibility_findings": findings}
