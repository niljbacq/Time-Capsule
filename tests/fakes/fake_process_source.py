from session_snapshot.models.adapter_types import ProcessInfo


class FakeProcessSource:
    def __init__(self, processes: tuple[ProcessInfo, ...] | list[ProcessInfo] = ()) -> None:
        self._processes = tuple(processes)

    def snapshot(self) -> tuple[ProcessInfo, ...]:
        return self._processes
