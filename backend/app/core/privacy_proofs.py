from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

# RFC 3526 group 14 safe prime. The subgroup order is q=(p-1)/2.
_P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65381"
    "FFFFFFFFFFFFFFFF",
    16,
)
_Q = (_P - 1) // 2
_G = 2
_H = 5


def _challenge(task_id: str, commitment: int, a0: int, a1: int) -> int:
    material = json.dumps(
        {"task_id": task_id, "commitment": commitment, "a0": a0, "a1": a1},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return int.from_bytes(hashlib.sha256(material).digest(), "big") % _Q


def _branch_value(commitment: int, outcome: int) -> int:
    return commitment * pow(_H, -outcome, _P) % _P


def create_binary_outcome_proof(task_id: str, outcome: int, nonce: str) -> dict[str, Any]:
    """Create a Fiat-Shamir OR proof for hidden binary outcome 0 or 1.

    The caller must retain the nonce only if it wants to reproduce a proof;
    the server stores only the commitment and proof transcript, never outcome
    or nonce. This is a compact proof of membership in the two-value set.
    """
    if outcome not in (0, 1):
        raise ValueError("outcome must be 0 or 1")
    if len(nonce) < 32:
        raise ValueError("nonce must contain at least 32 characters")
    r = int.from_bytes(hashlib.sha256(nonce.encode()).digest(), "big") % _Q
    commitment = pow(_G, r, _P) * pow(_H, outcome, _P) % _P
    true_branch = outcome
    false_branch = 1 - outcome
    c_false = secrets.randbelow(_Q)
    s_false = secrets.randbelow(_Q)
    y_false = _branch_value(commitment, false_branch)
    a_false = pow(_G, s_false, _P) * pow(y_false, -c_false, _P) % _P
    true_nonce = secrets.randbelow(_Q)
    a_true = pow(_G, true_nonce, _P)
    challenge = _challenge(
        task_id,
        commitment,
        a_true if true_branch == 0 else a_false,
        a_false if true_branch == 0 else a_true,
    )
    c_true = (challenge - c_false) % _Q
    s_true = true_nonce + c_true * r
    if true_branch == 0:
        c0, s0, a0 = c_true, s_true, a_true
        c1, s1, a1 = c_false, s_false, a_false
    else:
        c0, s0, a0 = c_false, s_false, a_false
        c1, s1, a1 = c_true, s_true, a_true
    return {
        "scheme": "oan-binary-outcome-or-schnorr-v1",
        "task_id": task_id,
        "commitment": str(commitment),
        "a0": str(a0),
        "a1": str(a1),
        "c0": str(c0),
        "s0": str(s0),
        "c1": str(c1),
        "s1": str(s1),
    }


def verify_binary_outcome_proof(proof: dict[str, Any]) -> bool:
    try:
        if proof.get("scheme") != "oan-binary-outcome-or-schnorr-v1":
            return False
        task_id = str(proof["task_id"])
        commitment = int(proof["commitment"])
        a0, a1 = int(proof["a0"]), int(proof["a1"])
        c0, c1 = int(proof["c0"]) % _Q, int(proof["c1"]) % _Q
        s0, s1 = int(proof["s0"]) % _Q, int(proof["s1"]) % _Q
        if not all(0 < value < _P for value in (commitment, a0, a1)):
            return False
        challenge = _challenge(task_id, commitment, a0, a1)
        if (c0 + c1) % _Q != challenge:
            return False
        y0 = _branch_value(commitment, 0)
        y1 = _branch_value(commitment, 1)
        return (
            pow(_G, s0, _P) == a0 * pow(y0, c0, _P) % _P
            and pow(_G, s1, _P) == a1 * pow(y1, c1, _P) % _P
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
