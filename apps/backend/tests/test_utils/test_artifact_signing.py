"""Tests for HMAC artifact signing (issue #266)."""

import importlib

from app.utils import artifact_signing
from app.utils.artifact_signing import sign_bytes, verify_bytes


class TestArtifactSigning:
    def test_sign_then_verify_roundtrip(self):
        data = b"\x80\x04arbitrary joblib bytes"
        sig = sign_bytes(data)
        assert verify_bytes(data, sig) is True

    def test_tampered_bytes_fail_verification(self):
        sig = sign_bytes(b"original artifact")
        assert verify_bytes(b"malicious artifact", sig) is False

    def test_missing_signature_fails(self):
        assert verify_bytes(b"data", None) is False
        assert verify_bytes(b"data", "") is False

    def test_wrong_signature_fails(self):
        assert verify_bytes(b"data", "deadbeef") is False

    def test_non_ascii_signature_returns_false_not_raises(self):
        # A signature built from attacker bytes may contain non-ASCII chars, which
        # would make hmac.compare_digest raise; verify must return False instead.
        assert verify_bytes(b"data", "�� bad sig") is False

    def test_signature_is_deterministic_and_hex(self):
        sig = sign_bytes(b"data")
        assert sig == sign_bytes(b"data")
        assert len(sig) == 64  # sha256 hex digest
        int(sig, 16)  # raises if not hex

    def test_key_precedence_and_env_change(self, monkeypatch):
        # ARTIFACT_SIGNING_KEY wins over NEXTAUTH_SECRET.
        monkeypatch.setenv("ARTIFACT_SIGNING_KEY", "key-a")
        monkeypatch.setenv("NEXTAUTH_SECRET", "key-b")
        sig_a = sign_bytes(b"data")

        # Different secret → different signature; the old sig no longer verifies.
        monkeypatch.delenv("ARTIFACT_SIGNING_KEY")
        sig_b = sign_bytes(b"data")
        assert sig_a != sig_b
        assert verify_bytes(b"data", sig_a) is False
        assert verify_bytes(b"data", sig_b) is True

    def test_falls_back_to_dev_key_when_unset(self, monkeypatch):
        monkeypatch.delenv("ARTIFACT_SIGNING_KEY", raising=False)
        monkeypatch.delenv("NEXTAUTH_SECRET", raising=False)
        # Reload to reset the one-shot warning flag; signing must still work.
        importlib.reload(artifact_signing)
        sig = artifact_signing.sign_bytes(b"data")
        assert artifact_signing.verify_bytes(b"data", sig) is True
