import logging
import stat

from session_snapshot.config.logging_setup import (
    LOGGER_NAME,
    attach_event_logging,
    setup_logging,
)
from session_snapshot.core.events import EventBus, EventKind


def _remove_file_handlers():
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_log_file_and_directory_are_private(tmp_path):
    try:
        path = setup_logging(tmp_path / "logs")
        logging.getLogger(LOGGER_NAME).info("hello")
        assert path.exists()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        assert "hello" in path.read_text()
    finally:
        _remove_file_handlers()


def test_setup_logging_is_idempotent(tmp_path):
    try:
        setup_logging(tmp_path / "logs")
        setup_logging(tmp_path / "logs")
        handlers = [
            h
            for h in logging.getLogger(LOGGER_NAME).handlers
            if getattr(h, "_session_snapshot_path", None)
        ]
        assert len(handlers) == 1
    finally:
        _remove_file_handlers()


def test_failed_results_are_logged_as_warnings(caplog):
    bus = EventBus()
    attach_event_logging(bus)
    with caplog.at_level(logging.INFO, logger=f"{LOGGER_NAME}.events"):
        bus.emit(EventKind.APP_RESULT, "x: failed", app="x", status="failed", reason="timeout")
        bus.emit(EventKind.APP_RESULT, "y: restored", app="y", status="restored", reason="ok")
    assert any(r.levelno == logging.WARNING and "x: failed" in r.getMessage() for r in caplog.records)
    assert any(r.levelno == logging.INFO and "y: restored" in r.getMessage() for r in caplog.records)
