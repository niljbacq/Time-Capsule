"""Main application window for the GUI shell.

Pure Qt presentation: a sidebar, a stack of five pages, the theme stylesheet,
and window geometry persisted through SettingsStore. Navigation decisions are
made by NavigationState, never here. Nothing in this module imports core/.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from session_snapshot.gui import styles
from session_snapshot.gui.navigation import (
    NAV_ITEMS,
    NavigationState,
    page_index,
)
from session_snapshot.gui.settings import MIN_WINDOW_SIZE, GuiSettings, SettingsStore
from session_snapshot.gui.sidebar import Sidebar
from session_snapshot.gui.controllers.sessions_controller import SessionsController
from session_snapshot.gui.sessions_page import SessionsPage
from session_snapshot.services.factory import create_default_service
from session_snapshot.gui.theme import (
    Palette,
    normalize_preference,
    palette_for,
    resolve_mode,
)

WINDOW_TITLE = "Session Snapshot"
CONTENT_MARGIN = 24


def system_is_dark() -> bool:
    """Whether the desktop currently prefers a dark appearance."""
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return False


def palette_for_preference(preference: object, system_dark: bool | None = None) -> Palette:
    """Resolve a theme preference (system/light/dark) to a palette."""
    if system_dark is None:
        system_dark = system_is_dark()
    return palette_for(resolve_mode(preference, system_dark))


class MainWindow(QMainWindow):
    """Shell window: sidebar plus one page per navigation entry."""

    def __init__(
        self,
        store: SettingsStore | None = None,
        parent: QWidget | None = None,
        *,
        sessions_controller: SessionsController | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store if store is not None else SettingsStore()
        self._settings: GuiSettings = self._store.load()
        self._state = NavigationState(collapsed=self._settings.sidebar_collapsed)
        self._pages: dict[str, QWidget] = {}
        self.save_error: OSError | None = None
        self._sessions_controller = (
            sessions_controller
            if sessions_controller is not None
            else SessionsController(create_default_service())
        )
        self._sessions_page: SessionsPage | None = None

        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(*MIN_WINDOW_SIZE)
        self._build()
        self._connect()
        self.apply_theme(self._settings.theme)
        self._apply_state()
        self.restore_geometry()

    # -- construction -----------------------------------------------------

    def _build(self) -> None:
        central = QWidget(self)
        central.setObjectName(styles.CONTENT)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = Sidebar(palette_for_preference(self._settings.theme), self._state, central)
        self._stack = QStackedWidget(central)
        self._stack.setObjectName("PageStack")
        for item in NAV_ITEMS:
            if item.id == "sessions":
                page: QWidget = SessionsPage(self._sessions_controller, central)
                self._sessions_page = page
            else:
                page = self._build_page(item.label)
            self._pages[item.id] = page
            self._stack.addWidget(page)

        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(central)

    def _build_page(self, title: str) -> QWidget:
        page = QWidget(self)
        page.setObjectName(styles.CONTENT)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN)
        label = QLabel(title, page)
        label.setObjectName(styles.PAGE_TITLE)
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _connect(self) -> None:
        self._sidebar.page_selected.connect(self.show_page)
        self._sidebar.collapsed_changed.connect(self._on_collapsed_changed)

    # -- navigation -------------------------------------------------------

    def show_page(self, page_id: object) -> bool:
        """Switch pages via NavigationState; return False for unknown ids."""
        if not self._state.select(page_id):
            return False
        self._stack.setCurrentIndex(page_index(self._state.active))
        self._sidebar.set_active(self._state.active)
        return True

    def _on_collapsed_changed(self, collapsed: bool) -> None:
        self._state.set_collapsed(collapsed)
        self._settings = replace(self._settings, sidebar_collapsed=self._state.collapsed)

    def _apply_state(self) -> None:
        self._sidebar.set_collapsed(self._state.collapsed)
        self._sidebar.set_active(self._state.active)
        self._stack.setCurrentIndex(page_index(self._state.active))

    # -- theme ------------------------------------------------------------

    def apply_theme(self, preference: object = None) -> Palette:
        """Apply a theme preference (None keeps the stored one); return the palette."""
        if preference is None:
            preference = self._settings.theme
        self._settings = replace(self._settings, theme=normalize_preference(preference))
        palette = palette_for_preference(self._settings.theme)
        self.setStyleSheet(styles.build_stylesheet(palette))
        self._sidebar.set_palette(palette)
        return palette

    # -- geometry ---------------------------------------------------------

    def restore_geometry(self) -> None:
        """Apply the stored window size, position and maximized state."""
        s = self._settings
        self.resize(s.window_width, s.window_height)
        if s.window_x is not None and s.window_y is not None:
            self.move(s.window_x, s.window_y)
        if s.window_maximized:
            self.setWindowState(self.windowState() | Qt.WindowMaximized)

    def current_settings(self) -> GuiSettings:
        """Settings snapshot including the live window geometry and sidebar state."""
        maximized = bool(self.windowState() & Qt.WindowMaximized)
        if maximized:
            normal = self.normalGeometry()
            geometry = normal if normal.width() > 0 and normal.height() > 0 else self.geometry()
        else:
            geometry = self.geometry()
        return replace(
            self._settings,
            window_width=geometry.width(),
            window_height=geometry.height(),
            window_x=geometry.x(),
            window_y=geometry.y(),
            window_maximized=maximized,
            sidebar_collapsed=self._state.collapsed,
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self._settings = self.current_settings()
        try:
            self._store.save(self._settings)
        except OSError as exc:
            self.save_error = exc
        else:
            self.save_error = None
        super().closeEvent(event)

    # -- accessors (used by controllers and tests) ------------------------

    @property
    def sidebar(self) -> Sidebar:
        return self._sidebar

    @property
    def stack(self) -> QStackedWidget:
        return self._stack

    @property
    def state(self) -> NavigationState:
        return self._state

    @property
    def sessions_page(self) -> SessionsPage | None:
        return self._sessions_page

    def page(self, page_id: str) -> QWidget | None:
        return self._pages.get(page_id)

    def current_page_id(self) -> str:
        return self._state.active
