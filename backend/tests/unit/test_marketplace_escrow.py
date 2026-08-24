from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.marketplace import MarketplaceEscrow, MarketplaceListing
from app.models.task import Task
from app.schemas.marketplace import (
    MarketplaceEscrowActionRequest,
    MarketplaceEscrowCreateRequest,
)
from app.services.marketplace.service import MarketplaceService


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _DB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []

    async def execute(self, _statement):
        return _Result(self.results.pop(0))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if isinstance(value, MarketplaceEscrow):
                value.id = value.id or uuid.uuid4()
                value.created_at = value.created_at or datetime.now(UTC)
                value.updated_at = value.updated_at or datetime.now(UTC)


def _listing(seller_id: uuid.UUID) -> MarketplaceListing:
    return MarketplaceListing(id=uuid.uuid4(), agent_id=seller_id, title="Summarizer")


def _escrow(buyer_id: uuid.UUID, seller_id: uuid.UUID, status: str = "held") -> MarketplaceEscrow:
    return MarketplaceEscrow(
        id=uuid.uuid4(),
        listing_id=uuid.uuid4(),
        buyer_agent_id=buyer_id,
        seller_agent_id=seller_id,
        amount=Decimal("12.50"),
        currency="USD",
        status=status,
        metadata_={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_create_escrow_records_internal_hold_and_normalizes_currency(monkeypatch):
    buyer_id, seller_id = uuid.uuid4(), uuid.uuid4()
    listing = _listing(seller_id)
    events = []

    async def publish(event_type, payload):
        events.append((event_type, payload))

    monkeypatch.setattr("app.services.marketplace.service.publish_event", publish)
    db = _DB(listing, None)
    result = await MarketplaceService().create_escrow(
        db,
        str(buyer_id),
        str(listing.id),
        Decimal("12.50"),
        currency="usd",
        idempotency_key="checkout-1",
    )

    escrow = db.added[0]
    assert result["status"] == "held"
    assert result["amount"] == "12.50"
    assert escrow.currency == "USD"
    assert escrow.idempotency_key == "checkout-1"
    assert events[0][0] == "marketplace.escrow.held"


@pytest.mark.asyncio
async def test_create_escrow_idempotency_returns_existing_record(monkeypatch):
    buyer_id, seller_id = uuid.uuid4(), uuid.uuid4()
    listing = _listing(seller_id)
    existing = _escrow(buyer_id, seller_id)
    existing.listing_id = listing.id
    existing.idempotency_key = "retry-1"
    events = []

    async def publish(event_type, payload):
        events.append(event_type)

    monkeypatch.setattr("app.services.marketplace.service.publish_event", publish)
    db = _DB(listing, existing)
    result = await MarketplaceService().create_escrow(
        db, str(buyer_id), str(listing.id), "12.50", idempotency_key="retry-1"
    )

    assert result["escrow_id"] == str(existing.id)
    assert db.added == []
    assert events == []


@pytest.mark.asyncio
async def test_release_requires_successful_task_and_is_terminal(monkeypatch):
    buyer_id, seller_id = uuid.uuid4(), uuid.uuid4()
    escrow = _escrow(buyer_id, seller_id)
    task = Task(
        id=uuid.uuid4(),
        from_agent_id=buyer_id,
        to_agent_id=seller_id,
        capability_name="summarize",
        payload={},
        status="running",
    )
    escrow.task_id = task.id
    monkeypatch.setattr(
        "app.services.marketplace.service.publish_event", lambda *_args: _async_noop()
    )
    service = MarketplaceService()

    with pytest.raises(ValueError, match="successful task completion"):
        await service.release_escrow(_DB(escrow, task), str(escrow.id), str(buyer_id))

    task.status = "success"
    result = await service.release_escrow(_DB(escrow, task), str(escrow.id), str(buyer_id))
    assert result["status"] == "released"
    with pytest.raises(ValueError, match="cannot be released"):
        await service.release_escrow(_DB(escrow), str(escrow.id), str(buyer_id))


@pytest.mark.asyncio
async def test_dispute_then_admin_refund_and_unauthorized_mutation(monkeypatch):
    buyer_id, seller_id, outsider_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    escrow = _escrow(buyer_id, seller_id)
    monkeypatch.setattr(
        "app.services.marketplace.service.publish_event", lambda *_args: _async_noop()
    )
    service = MarketplaceService()

    with pytest.raises(PermissionError, match="buyer or seller"):
        await service.dispute_escrow(_DB(escrow), str(escrow.id), str(outsider_id), "bad output")

    result = await service.dispute_escrow(
        _DB(escrow), str(escrow.id), str(buyer_id), "Output did not meet the contract"
    )
    assert result["status"] == "disputed"
    assert result["metadata"]["dispute_reason"] == "Output did not meet the contract"

    result = await service.refund_escrow(
        _DB(escrow), str(escrow.id), "Dispute upheld", str(uuid.uuid4())
    )
    assert result["status"] == "refunded"
    assert result["settled_at"] is not None

    with pytest.raises(ValueError, match="cannot be refunded"):
        await service.refund_escrow(_DB(escrow), str(escrow.id), "duplicate")


def _async_noop():
    async def noop():
        return None

    return noop()


def test_escrow_schemas_validate_positive_amount_and_reason():
    request = MarketplaceEscrowCreateRequest(listing_id=str(uuid.uuid4()), amount="0.01")
    assert request.amount == Decimal("0.01")
    assert MarketplaceEscrowActionRequest(reason="service unavailable").reason == "service unavailable"
    with pytest.raises(ValueError):
        MarketplaceEscrowCreateRequest(listing_id=str(uuid.uuid4()), amount="0")
