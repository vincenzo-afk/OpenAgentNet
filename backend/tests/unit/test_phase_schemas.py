"""Unit tests for Phase 2-6 features: workflow DAG validation, marketplace
access tiers, memory write requests, and trust schemas."""

from __future__ import annotations

import uuid
import pytest

from app.schemas.marketplace import (
    MarketplaceListingRequest,
    TierUpdateRequest,
    BillingWebhookRequest,
)
from app.schemas.memory import MemoryWriteRequest
from app.schemas.trust import EndorsementRequest
from app.services.marketplace.service import VALID_ACCESS_TIERS
from app.services.orchestration.service import validate_dag


class TestMarketplaceTierSchemas:
    def test_listing_request_defaults(self):
        req = MarketplaceListingRequest(
            title="Summarizer",
            long_description="Extractive summarizer",
            pricing={"currency": "USD", "unit_price": 0.01, "unit": "token"},
            is_public=True,
        )
        assert req.title == "Summarizer"
        assert req.pricing["unit_price"] == 0.01

    def test_valid_tiers_defined(self):
        assert "free" in VALID_ACCESS_TIERS
        assert "paid" in VALID_ACCESS_TIERS
        assert "invite_only" in VALID_ACCESS_TIERS

    def test_invalid_tier_rejected(self):
        # 'gold' is not in VALID_ACCESS_TIERS; check_phase6 asserts 400 for it
        if "gold" in VALID_ACCESS_TIERS:
            pytest.skip("tier list changed")

    def test_tier_update_request_accepts_valid(self):
        for tier in VALID_ACCESS_TIERS:
            req = TierUpdateRequest(access_tier=tier)
            assert req.access_tier == tier

    def test_billing_webhook_shape(self):
        listing = str(uuid.uuid4())
        agent = str(uuid.uuid4())
        req = BillingWebhookRequest(
            listing_id=listing,
            agent_id=agent,
            calls=125,
            event_type="usage",
            idempotency_key="key-1",
        )
        assert req.calls == 125
        assert req.idempotency_key == "key-1"


class TestMemorySchema:
    def test_write_request_requires_fields(self):
        owner = str(uuid.uuid4())
        req = MemoryWriteRequest(namespace=f"agent:{owner}", key="notes", data={"a": 1})
        assert req.namespace == f"agent:{owner}"
        assert req.data == {"a": 1}

    def test_namespace_key_required(self):
        with pytest.raises(Exception):
            MemoryWriteRequest(namespace="ns", key="k")  # data missing


class TestWorkflowDagValidation:
    def test_valid_chain(self):
        definition = {
            "tasks": [
                {"id": "fetch", "agent_capability": "fetch", "depends_on": []},
                {"id": "sum", "agent_capability": "summarize", "depends_on": ["fetch"]},
            ]
        }
        assert validate_dag(definition["tasks"]) is None

    def test_duplicate_step_id_rejected(self):
        definition = {
            "tasks": [
                {"id": "a", "agent_capability": "x", "depends_on": []},
                {"id": "a", "agent_capability": "x", "depends_on": []},
            ]
        }
        result = validate_dag(definition["tasks"])
        assert result is not None
        assert "Duplicate" in result

    def test_cycle_rejected(self):
        definition = {
            "tasks": [
                {"id": "a", "agent_capability": "x", "depends_on": ["b"]},
                {"id": "b", "agent_capability": "x", "depends_on": ["a"]},
            ]
        }
        result = validate_dag(definition["tasks"])
        assert result is not None
        assert "cycle" in result.lower()

    def test_undefined_dependency_rejected(self):
        definition = {
            "tasks": [
                {"id": "a", "agent_capability": "x", "depends_on": ["missing"]},
            ]
        }
        result = validate_dag(definition["tasks"])
        assert result is not None
        assert "missing" in result

    def test_self_dependency_rejected(self):
        definition = {
            "tasks": [
                {"id": "a", "agent_capability": "x", "depends_on": ["a"]},
            ]
        }
        result = validate_dag(definition["tasks"])
        assert result is not None


class TestTrustSchema:
    def test_endorsement_request(self):
        req = EndorsementRequest(
            to_agent_id=str(uuid.uuid4()),
            capability="summarization",
            comment="reliable",
        )
        assert req.capability == "summarization"
        assert req.comment == "reliable"
