from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TrustComponentFunction(Protocol):
    def __call__(self, record: Any) -> float: ...


@dataclass(frozen=True)
class TrustComponent:
    name: str
    weight: float
    compute: TrustComponentFunction
    description: str = ""


class TrustComponentRegistry:
    """In-process registry for trusted, operator-installed score components."""

    def __init__(self) -> None:
        self._components: dict[str, TrustComponent] = {}
        self._plugins_loaded = False

    def register(
        self,
        name: str,
        weight: float,
        compute: TrustComponentFunction,
        description: str = "",
    ) -> TrustComponent:
        if not name or weight <= 0:
            raise ValueError("Trust component name and positive weight are required")
        component = TrustComponent(name=name, weight=float(weight), compute=compute, description=description)
        self._components[name] = component
        return component

    def list(self) -> list[TrustComponent]:
        self._load_plugins()
        return list(self._components.values())

    def _load_plugins(self) -> None:
        if self._plugins_loaded:
            return
        self._plugins_loaded = True
        modules = [item.strip() for item in get_settings().trust_plugin_modules.split(",") if item.strip()]
        for module_name in modules:
            try:
                module = importlib.import_module(module_name)
                hook = getattr(module, "register_trust_components", None)
                if not callable(hook):
                    logger.warning("Trust plugin %s has no register_trust_components hook", module_name)
                    continue
                hook(self)
            except Exception:
                logger.exception("Unable to load trust plugin %s", module_name)


registry = TrustComponentRegistry()


def _register_defaults() -> None:
    settings = get_settings()
    registry.register("outcome_rate", settings.trust_weight_outcome, lambda record: float(record.outcome_rate), "Successful task ratio")
    registry.register(
        "latency_adherence",
        settings.trust_weight_latency,
        lambda record: float(
            getattr(record, "_latency_adherence", None)
            if getattr(record, "_latency_adherence", None) is not None
            else (record.component_scores or {}).get("latency_adherence", 0.5)
        ),
        "Observed execution time relative to the requested or declared latency target",
    )
    registry.register("dispute_health", settings.trust_weight_dispute, lambda record: 1.0 - float(record.dispute_penalty), "Inverse verified dispute penalty")
    registry.register("age_factor", settings.trust_weight_age, lambda record: float(record.age_factor), "Account age confidence factor")


_register_defaults()


def register_trust_component(
    name: str,
    weight: float,
    compute: TrustComponentFunction,
    description: str = "",
) -> TrustComponent:
    return registry.register(name, weight, compute, description)


def get_trust_components() -> list[TrustComponent]:
    return registry.list()
