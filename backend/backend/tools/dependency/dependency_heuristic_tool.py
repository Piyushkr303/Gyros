from __future__ import annotations

import re
from typing import Any

from backend.tools.base import Tool

_REQUIREMENT_LINE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+)\s*(==|>=|<=|~=|!=|>|<)?\s*([A-Za-z0-9_.\-]*)\s*$"
)

# Small curated "known safe minimum" baseline for a handful of widely-used
# packages, purely for demo/heuristic purposes - no network calls, no API
# keys. Upgrades cleanly to a real OSV/Dependabot lookup later.
_MIN_SAFE_VERSION: dict[str, tuple[int, ...]] = {
    "requests": (2, 20, 0),
    "pyyaml": (5, 1),
    "flask": (1, 0),
    "django": (2, 2),
    "jinja2": (2, 10, 1),
    "urllib3": (1, 24, 2),
    "cryptography": (3, 2),
}


def _parse_version(text: str) -> tuple[int, ...] | None:
    parts: list[int] = []
    for chunk in text.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) if parts else None


class DependencyHeuristicTool(Tool):
    """Deterministic requirements.txt-style heuristic: flags unpinned
    dependencies and pins older than a small curated safe-version baseline.
    Not a live vulnerability feed."""

    name = "dependency_heuristics"
    description = (
        "Scan added requirements.txt-style lines for unpinned or outdated dependency pins."
    )

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        added_line_texts: list[dict] = input.get("added_line_texts") or []
        findings: list[dict] = []

        for entry in added_line_texts:
            text = str(entry.get("text", "")).strip()
            if not text or text.startswith("#"):
                continue
            match = _REQUIREMENT_LINE.match(text)
            if not match:
                continue
            name, operator, version = match.groups()
            package = name.lower()

            if not operator:
                findings.append(
                    {
                        "lineno": entry.get("lineno"),
                        "type": "unpinned_dependency",
                        "message": f"Dependency '{name}' has no version pin, which risks non-reproducible builds.",
                    }
                )
                continue

            if operator in ("==", "<=", "~=") and package in _MIN_SAFE_VERSION and version:
                parsed = _parse_version(version)
                baseline = _MIN_SAFE_VERSION[package]
                if parsed is not None and parsed < baseline:
                    safe = ".".join(str(p) for p in baseline)
                    findings.append(
                        {
                            "lineno": entry.get("lineno"),
                            "type": "outdated_dependency",
                            "message": (
                                f"'{name}=={version}' is older than the {safe} baseline known to fix "
                                "published CVEs for this package; upgrade recommended."
                            ),
                        }
                    )

        return {"dependency_findings": findings}
