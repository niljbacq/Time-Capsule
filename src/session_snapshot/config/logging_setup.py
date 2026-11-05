import logging
import os
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

from session_snapshot.core.events import Event, EventBus, EventKind

LOGGER_NAME = "session_snapshot"


def default_log_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "linux-session-snapshot" / "logs"


class _PrivateRotatingFileHandler(RotatingFileHandler):
    """Rotating file handler whose files are always readable only by the owner."""

    def _open(self):
        stream = super()._open()
        os.chmod(self.baseFilename, 0o600)
        return stream


def setup_logging(log_dir: Path | None = None, level: int = logging.INFO) -> Path:
    """Attach a private rotating log file to the 'session_snapshot' logger.

    Safe to call more than once for the same directory.
    """
    directory = Path(log_dir) if log_dir else default_log_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / "session-snapshot.log"

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    for handler in logger.handlers:
        if getattr(handler, "_session_snapshot_path", None) == str(path):
            return path

    handler = _PrivateRotatingFileHandler(
        path, maxBytes=512_000, backupCount=3, encoding="utf-8"
    )
    handler._session_snapshot_path = str(path)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    return path


def attach_event_logging(bus: EventBus) -> Callable[[], None]:
    """Log every event from the bus. Failed and partial results are warnings."""
    log = logging.getLogger(f"{LOGGER_NAME}.events")

    def _log(event: Event) -> None:
        problem = event.kind is EventKind.APP_CAPTURE_FAILED or event.data.get(
            "status"
        ) in ("failed", "partial")
        log.log(
            logging.WARNING if problem else logging.INFO,
            "%s %s app=%s",
            event.kind.value,
            event.message,
            event.app,
        )

    return bus.subscribe(_log)
