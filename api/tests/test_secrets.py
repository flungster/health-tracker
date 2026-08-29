"""Tests for at-rest secret encryption (Fernet SecretsBox, M11a)."""

import pytest
from cryptography.fernet import Fernet

from app.security.secrets import SecretsBox, SecretsError


class TestSecretsBox:
    def test_generated_key_is_a_valid_fernet_key(self) -> None:
        key = SecretsBox.generate_key()
        Fernet(key)  # must be accepted by Fernet
        assert len(key) == 44  # 32 random bytes, urlsafe base64

    def test_generated_keys_are_unique(self) -> None:
        assert SecretsBox.generate_key() != SecretsBox.generate_key()

    def test_encrypt_decrypt_round_trip(self) -> None:
        box = SecretsBox(SecretsBox.generate_key())
        for plaintext in ("s3cret", "activity:read_all", "üñí¢ødé ✓", "a" * 2000):
            assert box.decrypt(box.encrypt(plaintext)) == plaintext

    def test_ciphertext_hides_plaintext_and_is_randomized(self) -> None:
        box = SecretsBox(SecretsBox.generate_key())
        first = box.encrypt("s3cret")
        second = box.encrypt("s3cret")
        assert "s3cret" not in first
        assert first != second  # fresh timestamp + IV per encryption
        assert box.decrypt(first) == box.decrypt(second) == "s3cret"

    def test_decrypt_with_wrong_key_fails(self) -> None:
        token = SecretsBox(SecretsBox.generate_key()).encrypt("s3cret")
        other_box = SecretsBox(SecretsBox.generate_key())
        with pytest.raises(SecretsError):
            other_box.decrypt(token)

    def test_decrypt_tampered_or_garbage_token_fails(self) -> None:
        box = SecretsBox(SecretsBox.generate_key())
        token = box.encrypt("s3cret")
        tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
        with pytest.raises(SecretsError):
            box.decrypt(tampered)
        with pytest.raises(SecretsError):
            box.decrypt("not-a-token")
        with pytest.raises(SecretsError):
            box.decrypt("")
