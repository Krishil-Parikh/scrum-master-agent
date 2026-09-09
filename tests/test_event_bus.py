from aamt.events.bus import EventBus
from aamt.models.event import EventType


def test_emit_query_and_subscribe(tmp_path):
    bus = EventBus(tmp_path / "events.db")
    seen = []
    unsub = bus.subscribe(seen.append)

    bus.emit(EventType.PROJECT_CREATED, project_id="P-1", name="demo")
    bus.emit(EventType.TASK_STARTED, project_id="P-1", task_id="T-1")
    bus.emit(EventType.TASK_COMPLETED, project_id="P-1", task_id="T-1")

    assert [e.type for e in seen] == [
        EventType.PROJECT_CREATED,
        EventType.TASK_STARTED,
        EventType.TASK_COMPLETED,
    ]
    assert bus.count(project_id="P-1") == 3
    assert len(bus.query(task_id="T-1")) == 2
    assert len(bus.query(types=[EventType.TASK_COMPLETED])) == 1

    unsub()
    bus.emit(EventType.PROJECT_COMPLETED, project_id="P-1")
    assert len(seen) == 3  # no longer notified
    bus.close()


def test_events_persist_across_reopen(tmp_path):
    db = tmp_path / "events.db"
    bus = EventBus(db)
    bus.emit(EventType.SPRINT_STARTED, project_id="P-1", sprint_id="S-1")
    bus.close()

    bus2 = EventBus(db)
    events = bus2.query(project_id="P-1")
    assert len(events) == 1
    assert events[0].type is EventType.SPRINT_STARTED
    assert events[0].sprint_id == "S-1"
    bus2.close()


def test_ordering_is_insertion_order(tmp_path):
    bus = EventBus(tmp_path / "e.db")
    for i in range(10):
        bus.emit(EventType.AGENT_PROGRESS_REPORTED, task_id="T-1", i=i)
    got = [e.payload["i"] for e in bus.query(task_id="T-1")]
    assert got == list(range(10))
    bus.close()
