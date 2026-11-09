"""Presentation controller for the Sessions library screen.

Wraps SessionService, caches the last SessionList, and records service
failures as a string so widgets never have to catch exceptions. Pure Python;
no Qt import.
"""

from __future__ import annotations

from session_snapshot.models.summaries import (
    SessionList,
    SessionProblem,
    SessionSummary,
)
from session_snapshot.report.models import RestorePreview, SaveReport
from session_snapshot.services.session_service import SessionService


class SessionsController:
    """Owns one SessionService and exposes only what the Sessions screen needs."""

    def __init__(self, service: SessionService) -> None:
        self._service = service
        self._sessions: list[SessionSummary] = []
        self._problems: list[SessionProblem] = []
        self._last_error: str | None = None
        self._loaded = False

    def refresh(self) -> SessionList:
        """Reload from the service. Never raises; a failure lands in last_error."""
        try:
            result = self._service.list_sessions()
        except Exception as exc:  # noqa: BLE001 — UI must not crash on service errors
            self._sessions = []
            self._problems = []
            self._last_error = str(exc) or type(exc).__name__
            self._loaded = True
            return SessionList()
        if result is None:
            self._sessions = []
            self._problems = []
            self._last_error = "service returned None"
            self._loaded = True
            return SessionList()
        self._sessions = list(result.sessions)
        self._problems = list(result.problems)
        self._last_error = None
        self._loaded = True
        return result

    @property
    def sessions(self) -> list[SessionSummary]:
        return list(self._sessions)

    @property
    def problems(self) -> list[SessionProblem]:
        return list(self._problems)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def is_empty(self) -> bool:
        return self._loaded and self._last_error is None and not self._sessions

    def rename_session(self, session_id: str, new_name: str) -> bool:
        try:
            self._service.rename_session(session_id, new_name)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc) or type(exc).__name__
            return False
        self._last_error = None
        return True

    def delete_session(self, session_id: str) -> bool:
        try:
            self._service.delete_session(session_id)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc) or type(exc).__name__
            return False
        self._last_error = None
        return True

    def save_session(
        self, session_id: str, name: str, description: str = ""
    ) -> SaveReport | None:
        try:
            report = self._service.save(session_id, name, description)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc) or type(exc).__name__
            return None
        self._last_error = None
        return report

    def save_session(
        self, session_id: str, name: str, description: str = ""
    ) -> SaveReport | None:
        try:
            report = self._service.save(session_id, name, description)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc) or type(exc).__name__
            return None
        self._last_error = None
        return report

    def preview(self, session_id: str) -> RestorePreview | None:
        try:
            return self._service.preview(session_id)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc) or type(exc).__name__
            return None

        try:
            self._service.rename_session(session_id, new_name)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc) or type(exc).__name__
            return False
        self._last_error = None
        return True

        try:
            self._service.delete_session(session_id)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc) or type(exc).__name__
            return False
        self._last_error = None
        return True

        try:
            self._service.rename_session(session_id, new_name)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc) or type(exc).__name__
            return False
        self._last_error = None
        return True

        try:
            self._service.delete_session(session_id)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc) or type(exc).__name__
            return False
        self._last_error = None
        return True
