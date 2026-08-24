from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_root(self, client: AsyncClient):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "OpenAgentNet"
        assert data["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_metrics_endpoint_and_request_id(self, client: AsyncClient):
        response = await client.get("/metrics", headers={"X-Request-ID": "integration-test-id"})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "integration-test-id"
        assert "openagentnet_http_requests_total" in response.text

    @pytest.mark.asyncio
    async def test_request_id_is_generated(self, client: AsyncClient):
        response = await client.get("/v1/health")
        UUID(response.headers["X-Request-ID"])
