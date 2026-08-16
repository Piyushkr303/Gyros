from __future__ import annotations

import re
from typing import Any

from backend.tools.base import Tool

_SECRET_PATTERN = re.compile(
    r"""(?ix)
    (api[_-]?key|secret|password|token|access[_-]?key)
    \s*[:=]\s*
    ['"][A-Za-z0-9_\-/+=]{8,}['"]
    """
)

_SQL_CONCAT_PATTERN = re.compile(
    r"""(?ix)
    (select|insert|update|delete)\b.*
    (\+\s*[a-zA-Z_][\w.]*|%s|f['"]|\.format\()
    """
)

_AUTH_CALL_PATTERN = re.compile(
    r"(?i)\b(authorize|authenticate|check_permission|require_auth|verify_access|has_permission)\w*\s*\("
)

_SENSITIVE_FUNCTION_DEF_PATTERN = re.compile(
    r"^([ \t]*)(?:async\s+)?def\s+(\w*(?:process_payment|transfer|delete_account|withdraw|charge)\w*)\s*\(",
    re.IGNORECASE,
)
_ANY_FUNCTION_DEF_PATTERN = re.compile(r"^([ \t]*)(?:async\s+)?def\s+\w+\s*\(")


def _function_body(lines: list[str], start_idx: int, indent: str) -> str:
    """Slice out a function's body (from its def line to the next sibling
    def/EOF at the same-or-lower indentation), so auth-call detection is
    scoped to that function rather than the whole file."""
    body_lines = [lines[start_idx]]
    for line in lines[start_idx + 1 :]:
        stripped = line.strip()
        if stripped:
            current_indent = line[: len(line) - len(line.lstrip(" \t"))]
            match = _ANY_FUNCTION_DEF_PATTERN.match(line)
            if match and len(current_indent) <= len(indent):
                break
        body_lines.append(line)
    return "\n".join(body_lines)


class RegexHeuristicTool(Tool):
    """Language-agnostic fallback analysis used when AST/semgrep aren't
    available for a given file. Flags hardcoded secrets, string-built SQL,
    and sensitive-action functions that have no nearby authorization call."""

    name = "regex_heuristics"
    description = (
        "Regex-based heuristics for secrets, SQL concatenation, and missing-authorization patterns."
    )

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        filename: str = input["filename"]
        added_line_texts: list[dict] = input.get("added_line_texts") or []
        full_text: str = input.get("source") or "\n".join(item["text"] for item in added_line_texts)

        findings: list[dict] = []

        for item in added_line_texts:
            text = item["text"]
            lineno = item["lineno"]
            if _SECRET_PATTERN.search(text):
                findings.append(
                    {
                        "type": "hardcoded_secret",
                        "lineno": lineno,
                        "text": text.strip(),
                        "message": "Line appears to contain a hardcoded secret/credential.",
                    }
                )
            if _SQL_CONCAT_PATTERN.search(text):
                findings.append(
                    {
                        "type": "sql_string_building",
                        "lineno": lineno,
                        "text": text.strip(),
                        "message": "SQL statement appears to be built via string concatenation/formatting.",
                    }
                )

        lines = full_text.splitlines()
        missing_auth_functions: list[str] = []
        for idx, line in enumerate(lines):
            match = _SENSITIVE_FUNCTION_DEF_PATTERN.match(line)
            if not match:
                continue
            indent, fn_name = match.group(1), match.group(2)
            body = _function_body(lines, idx, indent)
            if not _AUTH_CALL_PATTERN.search(body):
                missing_auth_functions.append(fn_name)

        return {
            "filename": filename,
            "regex_findings": findings,
            "has_auth_call": bool(_AUTH_CALL_PATTERN.search(full_text)),
            "missing_auth_functions": missing_auth_functions,
        }
