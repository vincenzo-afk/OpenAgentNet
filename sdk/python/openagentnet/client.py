from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any

import httpx


class OpenAgentNetError(RuntimeError):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"OpenAgentNet request failed ({status_code}): {detail}")


class OpenAgentNetClient:
    """Synchronous Python client for OpenAgentNet's versioned HTTP API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        token: str | None = None,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "OpenAgentNetClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, f"{self.base_url}{path}", headers=self._headers(), **kwargs)
        if not response.is_success:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise OpenAgentNetError(response.status_code, detail)
        if response.status_code == 204:
            return None
        return response.json()

    def register(self, identity: Mapping[str, Any], proof: Mapping[str, str]) -> dict[str, Any]:
        return self._request("POST", "/agents/register", json={"identity": identity, "proof": proof})

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        return self._request("GET", f"/agents/{agent_id}")

    def discover(
        self,
        capability: str | None = None,
        *,
        region: str | None = None,
        tags: list[str] | None = None,
        min_trust_score: float | None = None,
        limit: int = 10,
        sort: str = "trust_score:desc",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "sort": sort}
        if capability:
            params["capability"] = capability
        if region:
            params["region"] = region
        if tags:
            params["tags"] = ",".join(tags)
        if min_trust_score is not None:
            params["min_trust_score"] = min_trust_score
        return self._request("GET", "/discover", params=params)

    def send_task(
        self,
        executor_id: str,
        capability_slug: str,
        payload: Mapping[str, Any],
        *,
        constraints: Mapping[str, Any] | None = None,
        ttl_seconds: int = 60,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/tasks",
            json={
                "executor_id": executor_id,
                "capability_slug": capability_slug,
                "payload": dict(payload),
                "constraints": dict(constraints or {}),
                "ttl_seconds": ttl_seconds,
            },
        )

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/tasks/{task_id}")

    def route_task(
        self,
        task_description: str,
        required_capabilities: list[str] | None = None,
        *,
        constraints: Mapping[str, Any] | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/routing/route",
            json={
                "task_description": task_description,
                "required_capabilities": required_capabilities or [],
                "constraints": dict(constraints or {}),
                "limit": limit,
            },
        )

    def append_stream_chunk(
        self, task_id: str, sequence: int, chunk: Mapping[str, Any], *, is_final: bool = False
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/tasks/{task_id}/stream",
            json={"sequence": sequence, "chunk": dict(chunk), "is_final": is_final},
        )

    def stream_task_chunks(self, task_id: str) -> Iterator[dict[str, Any]]:
        with self._client.stream(
            "GET", f"{self.base_url}/tasks/{task_id}/stream", headers=self._headers()
        ) as response:
            if not response.is_success:
                detail = response.text
                raise OpenAgentNetError(response.status_code, detail)
            data_lines: list[str] = []
            for line in response.iter_lines():
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                elif not line and data_lines:
                    yield json.loads("\n".join(data_lines))
                    data_lines = []
            if data_lines:
                yield json.loads("\n".join(data_lines))

    def list_agent_versions(self, agent_id: str, *, limit: int = 50) -> dict[str, Any]:
        return self._request("GET", f"/agents/{agent_id}/versions", params={"limit": limit})

    def diff_agent_versions(self, agent_id: str, from_revision: int, to_revision: int) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/agents/{agent_id}/diff",
            params={"from_revision": from_revision, "to_revision": to_revision},
        )

    def create_privacy_proof(self, task_id: str, outcome: int, nonce: str) -> dict[str, Any]:
        return self._request(
            "POST", f"/tasks/{task_id}/privacy-proof", json={"outcome": outcome, "nonce": nonce}
        )

    def verify_privacy_proof(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/tasks/{task_id}/privacy-proof/verify")
