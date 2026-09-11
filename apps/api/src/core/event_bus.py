"""
Minimal in-process publish/subscribe event bus.

This is an in-process decoupling mechanism only: handlers run in the same
event loop, in the same process, as whatever code calls ``emit``. It is not
durable — there is no persistence or retry, so a process crash (or an
unhandled exception) mid-handler loses the event and any handlers that had
not yet run for it. That tradeoff is intentional: this project targets a
single-VPS, non-commercial deployment where a real message broker (Redis
Streams, RabbitMQ, etc.) would be operational overhead with no payoff.
Reach for one of those if events ever need to survive a restart or be
processed out-of-process.

Note: this module is named ``event_bus.py`` rather than ``events.py``
because ``src/core/events/`` already exists as an unrelated package (FastAPI
startup/shutdown lifecycle hooks) — a same-named ``src/core/events.py``
module would be shadowed by that package and never importable.
"""

from typing import Awaitable, Callable, Dict, List

Handler = Callable[[dict], Awaitable[None]]


class EventBus:
    """Registers async handlers by event name and awaits them on emit."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Handler]] = {}

    def on(self, event: str) -> Callable[[Handler], Handler]:
        """Decorator: register `handler` for `event`, returning it unchanged."""

        def register(handler: Handler) -> Handler:
            self._handlers.setdefault(event, []).append(handler)
            return handler

        return register

    async def emit(self, event: str, payload: dict) -> None:
        """Await every handler registered for `event`, in registration order."""
        for handler in self._handlers.get(event, []):
            await handler(payload)


bus = EventBus()
