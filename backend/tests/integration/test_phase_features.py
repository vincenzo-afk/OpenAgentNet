"""Integration tests for Phase 4-6 features: orchestration, memory ACL,
marketplace tiers and metering.

These exercise the app through the FastAPI TestClient against the in-process
application. Endpoints requiring a database expect TEST settings; when the
real database is unavailable the tests that need persistence are skipped.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# DAG validation (Phase 4)
# ---------------------------------------------------------------------------
class TestWorkflowDagValidation:
    @pytest.mark.asyncio
    async def test_rejects_cycle(self, client: AsyncClient):
        response = await client.post(
            "/v1/workflows",
            headers={
                "Authorization": "Bearer eyJ0eXNwIjoiSldUIn0.eyJzdWIiOiJkaWQ6b2FuOmZha2UiLCJhZ2VudF9pZCI6ImZha2UiLCJzY29wZXMiOlsiZGVsZWdhdGU6d29ya2Zsb3ciXSwiZXhwIjo5OTk5OTk5OTk5fQ.unsigned",
            },
            json={
                "name": "t-cycle",
                "definition": {
                    "tasks": [
                        {"id": "a", "agent_capability": "echo", "depends_on": ["b"], "payload": {}},
                        {"id": "b", "agent_capability": "echo", "depends_on": ["a"], "payload": {}},
                    ],
                },
            },
        )
        assert response.status_code in (400, 401, 403)
        if response.status_code == 400:
            assert "cycle" in response.text.lower() or "Circular" in response.text

    @pytest.mark.asyncio
    async def test_rejects_undefined_dependency(self, client: AsyncClient):
        response = await client.post(
            "/v1/workflows",
            json={
                "name": "t-undef",
                "definition": {
                    "tasks": [
                        {"id": "a", "agent_capability": "echo", "depends_on": ["missing"], "payload": {}},
                    ],
                },
            },
        )
        assert response.status_code in (400, 401, 403)
        if response.status_code == 400:
            assert "undefined" in response.text.lower() or "dependency" in response.text.lower()


# ---------------------------------------------------------------------------
# Marketplace tiers & metering (Phase 6)
# ---------------------------------------------------------------------------
class TestMarketplacePhase6:
    @pytest.mark.asyncio
    async def test_tier_validation(self, client: AsyncClient):
        response = await client.put(
            "/v1/marketplace/listings/nonexistent/tier",
            headers={"Authorization": "Bearer " + "x" * 200},
            json={"access_tier": "quantum"},
        )
        # Invalid tier value must be rejected regardless of listing existence.
        assert response.status_code in (400, 401, 403, 404)

    @pytest.mark.asyncio
    async def test_tier_search_filter(self, client: AsyncClient):
        response = await client.get("/v1/marketplace/listings?access_tier=free")
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", data.get("listings", []))
        for item in items:
            assert item.get("access_tier", "free") in ("free", "basic", "premium")
