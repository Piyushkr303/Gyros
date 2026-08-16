from __future__ import annotations

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_signature(payload_bytes: bytes, signature_header: str | None, secret: str) -> bool:
    """Validates GitHub's X-Hub-Signature-256 header (spec §51).

    If no secret is configured (mock mode - no keys available yet), the
    check is skipped and logged loudly rather than silently accepted, so the
    mock-mode posture is always visible in logs/traces.
    """
    if not secret:
        logger.warning("[MOCK] GITHUB_WEBHOOK_SECRET not set - skipping signature verification")
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = (
        "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header)
