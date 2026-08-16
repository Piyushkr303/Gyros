"""Simulates a real GitHub `pull_request.synchronize` webhook against the
locally-running backend, using the demo PR fixture's metadata. Computes a
real HMAC-SHA256 signature if GITHUB_WEBHOOK_SECRET is set. Streams the live
WebSocket event feed to stdout, and auto-approves the review when it reaches
the human-approval gate so the full pipeline (including GITHUB_UPDATED) is
observable in one run.

Usage:
    python scripts/simulate_webhook.py
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

import httpx
import websockets
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "demo_pr"

load_dotenv(REPO_ROOT / ".env")

BACKEND_PORT = os.environ.get("BACKEND_PORT", "8000")
BASE_URL = f"http://localhost:{BACKEND_PORT}"
WS_URL = f"ws://localhost:{BACKEND_PORT}"
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

_TERMINAL_EVENTS = {"REVIEW_COMPLETED", "REVIEW_FAILED"}


def _build_payload() -> dict:
    meta = json.loads((FIXTURES_DIR / "pr_meta.json").read_text(encoding="utf-8"))
    owner, name = meta["repo"].split("/", 1)
    return {
        "action": meta.get("action", "synchronize"),
        "pull_request": {
            "number": meta["number"],
            "title": meta["title"],
            "body": meta.get("body", ""),
            "head": {"sha": meta["head_sha"]},
            "base": {"sha": meta["base_sha"]},
            "user": {"login": meta.get("author", "demo-developer")},
        },
        "repository": {"full_name": meta["repo"], "name": name, "owner": {"login": owner}},
    }


def _sign(body: bytes) -> str | None:
    if not WEBHOOK_SECRET:
        print("[simulate_webhook] GITHUB_WEBHOOK_SECRET not set - sending unsigned (mock mode will accept this)")
        return None
    digest = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def main() -> None:
    payload = _build_payload()
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-GitHub-Event": "pull_request"}
    signature = _sign(body)
    if signature:
        headers["X-Hub-Signature-256"] = signature

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/webhooks/github", content=body, headers=headers, timeout=30)
        resp.raise_for_status()
        review_id = resp.json()["review_id"]
        print(f"[simulate_webhook] Webhook accepted -> review_id={review_id}")

        async with websockets.connect(f"{WS_URL}/ws/reviews/{review_id}") as ws:
            async for raw in ws:
                event = json.loads(raw)
                print(f"[{event['type']}] {json.dumps(event['payload'])[:300]}")

                if event["type"] == "APPROVAL_REQUIRED":
                    print("[simulate_webhook] Auto-approving review...")
                    approve_resp = await client.post(f"{BASE_URL}/api/reviews/{review_id}/approve", timeout=30)
                    approve_resp.raise_for_status()

                if event["type"] in _TERMINAL_EVENTS:
                    print(f"[simulate_webhook] Review finished with {event['type']}")
                    break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except httpx.HTTPStatusError as exc:
        print(f"[simulate_webhook] HTTP error: {exc.response.status_code} {exc.response.text}", file=sys.stderr)
        sys.exit(1)
