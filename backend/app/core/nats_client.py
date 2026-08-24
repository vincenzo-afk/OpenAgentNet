"""NATS JetStream client for agent-to-agent messaging.

Design decisions (see docs/DESIGN.md):
- Messaging transport: NATS JetStream with at-least-once delivery.
- Subjects:
  - `oan.messages.<agent_id>.inbox` — direct task delivery to an agent
  - `oan.events.>`               — workflow/trust/lifecycle events
  - `oan.agent.<agent_id>.announce` — heartbeat announcements
- Streams:
  - `OAN_TASKS`  -> `oan.messages.>`
  - `OAN_EVENTS` -> `oan.events.>`

This module is intentionally resilient: every public operation degrades
gracefully when NATS is unavailable so the platform can run with HTTP-only
delivery (e.g. in local development without a broker).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from nats.aio.client import Client as NATSClient

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_nats: NATSClient | None = None
_jetstream: Any | None = None
_consumers: list[Any] = []


class NatsUnavailableError(Exception):
    """Raised when NATS is configured but unreachable."""


def _subject_for_agent(agent_id: str) -> str:
    return f"oan.messages.{agent_id}.inbox"


EVENT_SUBJECT = "oan.events.{category}"


async def connect_nats() -> None:
    """Establish a single shared NATS connection with JetStream."""
    global _nats, _jetstream
    if _nats is not None and _nats.is_connected:
        return
    settings = get_settings()
    _nats = NATSClient()

    async def error_cb(err: Exception) -> None:
        logger.error("NATS error: %s", err)

    async def closed_cb() -> None:
        logger.warning("NATS connection closed")

    try:
        await _nats.connect(
            settings.nats_url,
            name=f"{settings.registry_id}@{settings.region}",
            connect_timeout=5,
            max_reconnect_attempts=3,
            error_cb=error_cb,
            closed_cb=closed_cb,
        )
        _jetstream = _nats.jetstream()
        logger.info("Connected to NATS at %s", settings.nats_url)
    except Exception:
        _nats = None
        _jetstream = None
        logger.warning("NATS unavailable at %s — falling back to HTTP delivery", settings.nats_url)


async def disconnect_nats() -> None:
    global _nats, _jetstream, _consumers
    for consumer in _consumers:
        try:
            await consumer.unsubscribe()
        except Exception:
            pass
    _consumers.clear()
    if _nats is not None:
        try:
            await _nats.drain()
        except Exception:
            try:
                await _nats.close()
            except Exception:
                pass
    _nats = None
    _jetstream = None


def is_nats_available() -> bool:
    return _nats is not None and _nats.is_connected


async def _ensure_stream(name: str, subject: str) -> None:
    """Create a JetStream stream if it does not exist."""
    if not _jetstream:
        return
    try:
        streams = await _jetstream.streams_info()
        names = [info.config.name for info in streams]
    except Exception:
        names = []
    if name not in names:
        try:
            await _jetstream.add_stream(name=name, subjects=[subject])
            logger.info("Created JetStream stream %s -> %s", name, subject)
        except Exception:
            logger.exception("Failed to create JetStream stream %s", name)


async def publish_to_agent(agent_id: str, envelope: dict[str, Any]) -> bool:
    """Publish a task envelope to an agent's inbox subject via JetStream.

    Returns True if published to NATS, False if NATS is unavailable
    (caller should fall back to HTTP delivery).
    """
    if not is_nats_available():
        return False
    await _ensure_stream("OAN_TASKS", "oan.messages.>")
    try:
        ack = await _jetstream.publish(
            _subject_for_agent(agent_id),
            json.dumps(envelope, default=str).encode(),
            timeout=5,
        )
        logger.debug("NATS publish seq=%s stream=%s", ack.seq, ack.stream)
        return True
    except Exception:
        logger.exception("NATS publish failed for agent %s", agent_id)
        return False


async def publish_event(category: str, payload: dict[str, Any]) -> bool:
    """Publish a platform event (workflow status, trust changes, etc.)."""
    if not is_nats_available():
        return False
    await _ensure_stream("OAN_EVENTS", "oan.events.>")
    subject = EVENT_SUBJECT.format(category=category)
    try:
        await _jetstream.publish(
            subject,
            json.dumps(payload, default=str).encode(),
            timeout=5,
        )
        return True
    except Exception:
        logger.exception("NATS event publish failed: %s", category)
        return False


async def publish_agent_announce(agent_id: str, payload: dict[str, Any]) -> bool:
    """Publish an agent heartbeat/announce event (PROTOCOL.md section 10)."""
    if not is_nats_available():
        return False
    subject = f"oan.agent.{agent_id}.announce"
    try:
        await _nats.publish(subject, json.dumps(payload, default=str).encode())
        return True
    except Exception:
        logger.exception("NATS announce publish failed for %s", agent_id)
        return False


async def subscribe_agent_inbox(
    agent_id: str,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
    wildcard: bool = False,
) -> Any:  # noqa: E501
    """Subscribe to an agent's inbox and invoke `handler` for each envelope.

    Returns the NATS subscription so callers can unsubscribe later.
    """
    if not is_nats_available():
        return None

    async def _msg_handler(msg: Any) -> None:
        envelope: dict = {}
        try:
            envelope = json.loads(msg.data.decode())
            await handler(envelope)
        except Exception:
            logger.exception("Error handling NATS inbox message for %s", agent_id)
        finally:
            try:
                await msg.ack()
            except Exception:
                pass

    subject = f"oan.messages.{agent_id}.inbox"
    if wildcard or agent_id == "+":
        subject = "oan.messages.+.inbox"
    await _ensure_stream("OAN_TASKS", "oan.messages.>")
    try:
        sub = await _jetstream.subscribe(
            subject,
            stream="OAN_TASKS",
            cb=_msg_handler,
            durable="inbox_listener" if (wildcard or agent_id == "+") else f"agent_{agent_id.replace('-', '_')}",
            manual_ack=True,
        )
        _consumers.append(sub)
        logger.info("Subscribed agent %s to %s", agent_id, _subject_for_agent(agent_id))
        return sub
    except Exception:
        logger.exception("Failed to subscribe agent %s", agent_id)
        return None
