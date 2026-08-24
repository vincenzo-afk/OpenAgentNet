from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.routing import RoutingRequest
from app.services.routing import select_best_candidate


def _candidate(agent_id: str, score: float) -> dict:
    return {"agent_id": agent_id, "score": score}


def test_select_best_candidate_returns_highest_ranked_candidate() -> None:
    candidates = [_candidate("a", 0.9), _candidate("b", 0.8)]
    assert select_best_candidate(candidates)["agent_id"] == "a"


def test_select_best_candidate_honors_valid_preference() -> None:
    candidates = [_candidate("a", 0.9), _candidate("b", 0.8)]
    assert select_best_candidate(candidates, preferred_id="b")["agent_id"] == "b"


def test_select_best_candidate_ignores_unknown_preference() -> None:
    candidates = [_candidate("a", 0.9)]
    assert select_best_candidate(candidates, preferred_id="missing")["agent_id"] == "a"


def test_routing_request_requires_description() -> None:
    with pytest.raises(ValidationError):
        RoutingRequest(task_description="")
