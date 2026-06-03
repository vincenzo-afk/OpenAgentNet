from __future__ import annotations

import hashlib
import base64
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.crypto import (
    generate_ed25519_keypair,
    compute_agent_id_from_bytes,
    public_key_to_bytes,
    public_key_to_base64,
    base64_to_public_key,
    sign_message,
    verify_signature,
    canonical_json_bytes,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)


class TestKeyGeneration:
    def test_generate_keypair(self):
        private_key, public_key = generate_ed25519_keypair()
        assert private_key is not None
        assert public_key is not None

    def test_public_key_to_bytes(self):
        _, public_key = generate_ed25519_keypair()
        pk_bytes = public_key_to_bytes(public_key)
        assert len(pk_bytes) == 32

    def test_public_key_to_base64(self):
        _, public_key = generate_ed25519_keypair()
        b64 = public_key_to_base64(public_key)
        assert b64.startswith("ed25519:")

    def test_base64_roundtrip(self):
        _, public_key = generate_ed25519_keypair()
        b64 = public_key_to_base64(public_key)
        recovered = base64_to_public_key(b64)
        assert public_key_to_bytes(recovered) == public_key_to_bytes(public_key)


class TestAgentId:
    def test_deterministic_id(self):
        _, public_key = generate_ed25519_keypair()
        pk_bytes = public_key_to_bytes(public_key)
        id1 = compute_agent_id_from_bytes(pk_bytes)
        id2 = compute_agent_id_from_bytes(pk_bytes)
        assert id1 == id2
        assert len(id1) == 24

    def test_different_keys_different_ids(self):
        _, pk1 = generate_ed25519_keypair()
        _, pk2 = generate_ed25519_keypair()
        id1 = compute_agent_id_from_bytes(public_key_to_bytes(pk1))
        id2 = compute_agent_id_from_bytes(public_key_to_bytes(pk2))
        assert id1 != id2


class TestSigning:
    def test_sign_and_verify(self):
        private_key, public_key = generate_ed25519_keypair()
        payload = b"test message"
        signature = sign_message(private_key, payload)
        assert signature.startswith("base64url:")
        assert verify_signature(public_key, signature, payload)

    def test_verify_wrong_message(self):
        private_key, public_key = generate_ed25519_keypair()
        signature = sign_message(private_key, b"correct message")
        assert not verify_signature(public_key, signature, b"wrong message")

    def test_verify_wrong_key(self):
        private_key1, _ = generate_ed25519_keypair()
        _, public_key2 = generate_ed25519_keypair()
        signature = sign_message(private_key1, b"message")
        assert not verify_signature(public_key2, signature, b"message")


class TestCanonicalJson:
    def test_sorted_keys(self):
        obj = {"b": 2, "a": 1, "c": 3}
        result = canonical_json_bytes(obj)
        assert result == b'{"a":1,"b":2,"c":3}'

    def test_no_whitespace(self):
        obj = {"key": "value", "nested": {"a": 1}}
        result = canonical_json_bytes(obj)
        assert b" " not in result


class TestApiKey:
    def test_generate_api_key(self):
        key = generate_api_key()
        assert key.startswith("oan_")
        assert len(key) > 10

    def test_hash_api_key(self):
        key = generate_api_key()
        h = hash_api_key(key)
        assert len(h) > 0  # Argon2id hash is not fixed length
        assert h != key  # hash is not the raw key
        # Argon2id hashes are not deterministic (random salt)
        h2 = hash_api_key(key)
        assert h != h2  # different hashes due to random salt

    def test_verify_api_key(self):
        key = generate_api_key()
        h = hash_api_key(key)
        assert verify_api_key(key, h)
        assert not verify_api_key("wrong_key", h)
