from __future__ import annotations

from app.core.privacy_proofs import create_binary_outcome_proof, verify_binary_outcome_proof


def test_binary_outcome_proof_verifies_for_success_and_failure() -> None:
    for outcome in (0, 1):
        proof = create_binary_outcome_proof("task-privacy", outcome, "n" * 32)
        assert verify_binary_outcome_proof(proof) is True
        assert "outcome" not in proof
        assert "nonce" not in proof


def test_binary_outcome_proof_rejects_tampering() -> None:
    proof = create_binary_outcome_proof("task-privacy", 1, "n" * 32)
    tampered = dict(proof)
    tampered["commitment"] = str(int(tampered["commitment"]) + 1)
    assert verify_binary_outcome_proof(tampered) is False
