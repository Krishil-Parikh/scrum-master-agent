import pytest

from app.communication.event_bus import EventBus
from app.schemas.event import EventType


@pytest.mark.asyncio
async def test_publish_reaches_subscribers():
    bus = EventBus()
    received = []

    async def subscriber(event):
        received.append(event)

    bus.subscribe(subscriber)
    await bus.emit(EventType.TASK_STARTED, actor_id="backend", task_id="t1")

    assert len(received) == 1
    assert received[0].type == EventType.TASK_STARTED
    assert received[0].payload["task_id"] == "t1"


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    bus = EventBus()
    received = []

    async def subscriber(event):
        received.append(event)

    bus.subscribe(subscriber)
    bus.unsubscribe(subscriber)
    await bus.emit(EventType.TASK_STARTED, actor_id="backend")

    assert received == []


@pytest.mark.asyncio
async def test_one_failing_subscriber_does_not_block_others():
    bus = EventBus()
    received = []

    async def bad_subscriber(event):
        raise RuntimeError("boom")

    async def good_subscriber(event):
        received.append(event)

    bus.subscribe(bad_subscriber)
    bus.subscribe(good_subscriber)
    await bus.emit(EventType.TASK_COMPLETED)

    assert len(received) == 1
