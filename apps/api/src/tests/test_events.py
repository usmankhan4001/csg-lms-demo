"""
Tests for the in-process pub/sub event bus (src/core/event_bus.py).

Each test builds a fresh EventBus() rather than using the module-level
`bus` singleton, so handler registrations don't leak across tests.
"""

import pytest

from src.core.event_bus import EventBus


@pytest.mark.asyncio
async def test_emit_calls_registered_handler_with_payload():
    events = EventBus()
    received = []

    @events.on("student.absence_streak")
    async def handler(payload: dict) -> None:
        received.append(payload)

    payload = {"student_id": 101, "streak": 3}
    await events.emit("student.absence_streak", payload)

    assert received == [payload]


@pytest.mark.asyncio
async def test_on_returns_handler_unchanged():
    events = EventBus()

    async def handler(payload: dict) -> None:
        pass

    registered = events.on("some.event")(handler)

    assert registered is handler


@pytest.mark.asyncio
async def test_emit_calls_multiple_handlers_in_registration_order():
    events = EventBus()
    call_order = []

    @events.on("some.event")
    async def first(payload: dict) -> None:
        call_order.append(("first", payload))

    @events.on("some.event")
    async def second(payload: dict) -> None:
        call_order.append(("second", payload))

    payload = {"key": "value"}
    await events.emit("some.event", payload)

    assert call_order == [("first", payload), ("second", payload)]


@pytest.mark.asyncio
async def test_emit_with_no_handlers_does_not_raise():
    events = EventBus()

    await events.emit("nobody.listening", {"anything": True})
