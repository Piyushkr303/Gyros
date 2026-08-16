from __future__ import annotations

import re
from typing import Any

import httpx

from backend.tools.base import Tool

_PINNED_REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*([A-Za-z0-9_.\-]+)\s*$")
_OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"


class OsvVulnerabilityTool(Tool):
    """Real vulnerability lookup against OSV.dev's public batch API
    (https://osv.dev - no API key required) for exact-pinned PyPI packages
    added in this diff. This is the OSV item from the spec's deferred-tool
    list, made real: it needs only network access, not a local binary, so it
    follows the same real/graceful-fallback shape as ruff/semgrep/pylint use
    for a missing binary, but degrades on network failure instead."""

    name = "osv_vulnerabilities"
    description = (
        "Query OSV.dev for known vulnerabilities in newly-pinned PyPI dependency versions."
    )

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        added_line_texts: list[dict] = input.get("added_line_texts") or []
        packages: list[tuple[str, str, int | None]] = []
        for entry in added_line_texts:
            text = str(entry.get("text", "")).strip()
            match = _PINNED_REQUIREMENT.match(text)
            if match:
                name, version = match.groups()
                packages.append((name, version, entry.get("lineno")))

        if not packages:
            return {"reachable": True, "vulnerabilities": []}

        queries = [
            {"package": {"name": name, "ecosystem": "PyPI"}, "version": version}
            for name, version, _ in packages
        ]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(_OSV_BATCH_URL, json={"queries": queries})
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError:
            return {"reachable": False, "vulnerabilities": []}

        vulnerabilities: list[dict] = []
        for (name, version, lineno), result in zip(
            packages, payload.get("results", []), strict=False
        ):
            for vuln in result.get("vulns") or []:
                vulnerabilities.append(
                    {
                        "package": name,
                        "version": version,
                        "lineno": lineno,
                        "id": vuln.get("id"),
                        "summary": vuln.get("summary", ""),
                    }
                )
        return {"reachable": True, "vulnerabilities": vulnerabilities}
