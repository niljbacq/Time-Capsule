from session_snapshot.core.events import EventBus, EventKind


def test_subscribers_receive_events_in_order():
    bus = EventBus()
    got = []
    bus.subscribe(got.append)
    bus.emit(EventKind.SAVE_STARTED, "one")
    bus.emit(EventKind.APP_CAPTURED, "two", app="x")
    bus.emit(EventKind.SAVE_FINISHED, "three")
    assert [e.message for e in got] == ["one", "two", "three"]
    assert got[1].app == "x"


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    got = []
    unsubscribe = bus.subscribe(got.append)
    bus.emit(EventKind.SAVE_STARTED, "one")
    unsubscribe()
    bus.emit(EventKind.SAVE_STARTED, "two")
    assert len(got) == 1


def test_failing_subscriber_does_not_break_others():
    bus = EventBus()
    got = []

    def bad(event):
        raise RuntimeError("boom")

    bus.subscribe(bad)
    bus.subscribe(got.append)
    bus.emit(EventKind.SAVE_STARTED, "x")
    assert len(got) == 1
