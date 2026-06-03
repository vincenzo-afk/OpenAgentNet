from __future__ import annotations

import base64
import hashlib
import secrets
import string

import base58
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from canonicaljson import encode_canonical_json
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# Argon2id hasher for API keys (SECURITY.md requirement)
_argon2_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def generate_ed25519_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def public_key_to_bytes(public_key: Ed25519PublicKey) -> bytes:
    return public_key.public_bytes_raw()


def public_key_to_base64(public_key: Ed25519PublicKey) -> str:
    return "ed25519:" + base64.b64encode(public_key_to_bytes(public_key)).decode()


def base64_to_public_key(key_str: str) -> Ed25519PublicKey:
    raw = base64.b64decode(key_str.removeprefix("ed25519:"))
    return Ed25519PublicKey.from_public_bytes(raw)


def compute_agent_id(public_key: Ed25519PublicKey) -> str:
    pk_bytes = public_key_to_bytes(public_key)
    digest = hashlib.sha256(pk_bytes).digest()
    return base58.b58encode(digest).decode()[:24]


def compute_agent_id_from_bytes(public_key_bytes: bytes) -> str:
    digest = hashlib.sha256(public_key_bytes).digest()
    return base58.b58encode(digest).decode()[:24]


def sign_message(private_key: Ed25519PrivateKey, payload: bytes) -> str:
    signature = private_key.sign(payload)
    return "base64url:" + base64.urlsafe_b64encode(signature).decode()


def verify_signature(public_key: Ed25519PublicKey, signature: str, payload: bytes) -> bool:
    try:
        sig_bytes = base64.urlsafe_b64decode(signature.removeprefix("base64url:"))
        public_key.verify(sig_bytes, payload)
        return True
    except Exception:
        return False


def canonical_json_bytes(obj: dict) -> bytes:
    return encode_canonical_json(obj)


def hash_api_key(raw_key: str) -> str:
    """Hash API key using Argon2id (SECURITY.md requirement)."""
    return _argon2_ph.hash(raw_key)


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    """Verify API key against Argon2id hash."""
    try:
        _argon2_ph.verify(key_hash, raw_key)
        return True
    except VerifyMismatchError:
        return False


def generate_api_key() -> str:
    """Generate API key: oan_ + 48 base62 characters (SECURITY.md requirement)."""
    alphabet = string.ascii_letters + string.digits  # base62
    random_part = "".join(secrets.choice(alphabet) for _ in range(48))
    return "oan_" + random_part
