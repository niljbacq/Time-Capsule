import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


class EventKind(str, Enum):
    SAVE_STARTED = "save_started"
    APP_DETECTED = "app_detected"
    APP_CAPTURED = "app_captured"
    APP_CAPTURE_FAILED = "app_capture_failed"
    APP_EXCLUDED = "app_excluded"
    SAVE_FINISHED = "save_finished"
    RESTORE_STARTED = "restore_started"
    APP_PLANNED = "app_planned"
    APP_RESTORING = "app_restoring"
    APP_RESULT = "app_result"
    RESTORE_FINISHED = "restore_finished"


@dataclass(frozen=True)
class Event:
    kind: EventKind
    message: str
    timestamp: float
    app: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """In-process event stream. The GUI, CLI and log file are just subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[Event], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, callback: Callable[[Event], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def emit(self, kind: EventKind, message: str, app: str | None = None, **data: Any) -> Event:
        event = Event(kind=kind, message=message, timestamp=time.time(), app=app, data=dict(data))
        with self._lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(event)
            except Exception:  # noqa: BLE001 - a bad subscriber must never break a save
                log.exception("event subscriber failed")
        return event
