from __future__ import annotations

import json
from typing import Any

import httpx
import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB

from app.core.config import get_settings
from app.models.agent import Agent
from app.models.trust import TrustRecord


def select_best_candidate(candidates: list[dict[str, Any]], preferred_id: str | None = None) -> dict[str, Any] | None:
    if preferred_id:
        preferred = next((item for item in candidates if item["agent_id"] == preferred_id), None)
        if preferred:
            return preferred
    return candidates[0] if candidates else None


class RoutingService:
    async def route(
        self,
        db: AsyncSession,
        task_description: str,
        required_capabilities: list[str],
        constraints: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        constraints = constraints or {}
        query = (
            select(Agent, func.coalesce(TrustRecord.trust_score, 0.5).label("trust_score"))
            .outerjoin(TrustRecord, TrustRecord.agent_id == Agent.id)
            .where(Agent.deleted_at.is_(None), Agent.status == "active")
        )
        target_region = constraints.get("region")
        if target_region:
            query = query.where(Agent.region == target_region)
        for capability in required_capabilities:
            query = query.where(
                Agent.capabilities.op("@>")(sa.cast([{"name": capability}], JSONB))
            )

        result = await db.execute(query)
        rows = result.all()
        required = set(required_capabilities)
        candidates: list[dict[str, Any]] = []
        for agent, trust_score in rows:
            names = {item.get("name") for item in (agent.capabilities or [])}
            matched = len(required & names)
            match_score = matched / len(required) if required else 1.0
            trust = float(trust_score or 0.5)
            score = round((match_score * 0.7) + (trust * 0.3), 6)
            reasons = [f"capability match {matched}/{len(required) or 0}", f"trust score {trust:.3f}"]
            if target_region:
                reasons.append(f"region match {agent.region}")
            candidates.append(
                {
                    "agent_id": str(agent.id),
                    "did": agent.did,
                    "name": agent.name,
                    "region": agent.region,
                    "trust_score": trust,
                    "capability_match": match_score,
                    "score": score,
                    "reasons": reasons,
                }
            )
        candidates.sort(key=lambda item: (-item["score"], item["name"]))
        candidates = candidates[:limit]

        preferred_id = await self._llm_select(task_description, required_capabilities, candidates)
        selected = select_best_candidate(candidates, preferred_id)
        strategy = "llm-assisted" if preferred_id and selected else "deterministic"
        rationale = (
            "Selected by configured routing model after capability and trust pre-filtering."
            if strategy == "llm-assisted"
            else "Selected by capability match first, then trust score, then stable name ordering."
        )
        return {
            "selected_agent_id": selected["agent_id"] if selected else None,
            "selected_did": selected["did"] if selected else None,
            "strategy": strategy,
            "candidates": candidates,
            "rationale": rationale,
        }

    async def _llm_select(
        self,
        task_description: str,
        required_capabilities: list[str],
        candidates: list[dict[str, Any]],
    ) -> str | None:
        settings = get_settings()
        if not settings.routing_llm_base_url or not settings.routing_llm_api_key or not candidates:
            return None
        prompt = {
            "task_description": task_description,
            "required_capabilities": required_capabilities,
            "candidates": candidates,
            "instruction": "Return JSON with exactly one key, selected_agent_id, using only a candidate id.",
        }
        try:
            async with httpx.AsyncClient(timeout=settings.routing_llm_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.routing_llm_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.routing_llm_api_key}"},
                    json={
                        "model": settings.routing_llm_model,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": "You route tasks to registered agents."},
                            {"role": "user", "content": json.dumps(prompt)},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                selected = json.loads(content).get("selected_agent_id")
                valid_ids = {candidate["agent_id"] for candidate in candidates}
                return selected if selected in valid_ids else None
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
