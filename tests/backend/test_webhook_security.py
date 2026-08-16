import hashlib
import hmac

from backend.integrations.github.webhook_security import verify_signature


def test_valid_signature_is_accepted():
    secret = "test-secret"
    body = b'{"action": "synchronize"}'
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    header = f"sha256={digest}"
    assert verify_signature(body, header, secret) is True


def test_invalid_signature_is_rejected():
    secret = "test-secret"
    body = b'{"action": "synchronize"}'
    assert verify_signature(body, "sha256=deadbeef", secret) is False


def test_missing_header_is_rejected_when_secret_configured():
    assert verify_signature(b"{}", None, "test-secret") is False


def test_malformed_header_is_rejected():
    assert verify_signature(b"{}", "not-a-real-signature", "test-secret") is False


def test_missing_secret_skips_check_in_mock_mode():
    # No secret configured (no keys available yet) - mock mode accepts, but
    # this must be an explicit, logged decision, not silent.
    assert verify_signature(b"{}", None, "") is True


def test_tampered_body_is_rejected():
    secret = "test-secret"
    original_body = b'{"action": "synchronize"}'
    digest = hmac.new(secret.encode(), original_body, hashlib.sha256).hexdigest()
    header = f"sha256={digest}"
    tampered_body = b'{"action": "opened"}'
    assert verify_signature(tampered_body, header, secret) is False
