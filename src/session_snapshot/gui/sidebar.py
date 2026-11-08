"""Collapsible navigation sidebar. NavigationState decides; this widget shows it."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from session_snapshot.gui import icons, navigation, styles
from session_snapshot.gui.navigation import NavigationState
from session_snapshot.gui.theme import Palette

EXPANDED_WIDTH = 220
COLLAPSED_WIDTH = 60
APP_TITLE = "Session Snapshot"
ICON_SIZE = 20


class Sidebar(QFrame):
    page_selected = Signal(str)
    collapsed_changed = Signal(bool)

    def __init__(
        self, palette: Palette, state: NavigationState, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._palette = palette
        self._state = state
        self.setObjectName(styles.SIDEBAR)

        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(4)
        self._title = QLabel(APP_TITLE)
        self._title.setObjectName(styles.APP_NAME)
        self._layout.addWidget(self._title)
        self._layout.addSpacing(8)

        self._buttons: dict[str, QPushButton] = {}
        for item in navigation.NAV_ITEMS:
            button = self._make_button()
            button.setAccessibleName(item.label)
            button.clicked.connect(
                lambda _checked=False, pid=item.id: self._on_nav_clicked(pid)
            )
            self._layout.addWidget(button)
            self._buttons[item.id] = button

        self._layout.addStretch(1)
        self._collapse = self._make_button()
        self._collapse.clicked.connect(lambda _checked=False: self._on_collapse_clicked())
        self._layout.addWidget(self._collapse)
        self.refresh()

    def _make_button(self) -> QPushButton:
        button = QPushButton()
        button.setObjectName(styles.NAV_BUTTON)
        button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("active", False)
        return button

    def button(self, page_id: str) -> QPushButton:
        return self._buttons[page_id]

    def collapse_button(self) -> QPushButton:
        return self._collapse

    def title_label(self) -> QLabel:
        return self._title

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.refresh()

    def set_active(self, page_id: str) -> bool:
        """Highlight a page without emitting page_selected."""
        if not self._state.select(page_id):
            return False
        self.refresh()
        return True

    def set_collapsed(self, collapsed: bool) -> None:
        """Collapse or expand without emitting collapsed_changed."""
        self._state.set_collapsed(collapsed)
        self.refresh()

    def _on_nav_clicked(self, page_id: str) -> None:
        if self._state.select(page_id):
            self.refresh()
            self.page_selected.emit(page_id)

    def _on_collapse_clicked(self) -> None:
        collapsed = self._state.toggle_collapsed()
        self.refresh()
        self.collapsed_changed.emit(collapsed)

    def refresh(self) -> None:
        """Bring every widget in line with the state and the palette."""
        collapsed = self._state.collapsed
        pal = self._palette
        side = 4 if collapsed else 8
        self._layout.setContentsMargins(side, 12, side, 12)
        self.setFixedWidth(COLLAPSED_WIDTH if collapsed else EXPANDED_WIDTH)
        self._title.setVisible(not collapsed)
        for item in navigation.NAV_ITEMS:
            button = self._buttons[item.id]
            active = item.id == self._state.active
            button.setText("" if collapsed else item.label)
            button.setToolTip(item.label if collapsed else "")
            color = pal.primary if active else pal.text
            button.setIcon(icons.render_icon(item.icon, color, ICON_SIZE))
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)
        if collapsed:
            self._collapse.setText("")
            self._collapse.setToolTip("Expand sidebar")
            self._collapse.setAccessibleName("Expand sidebar")
            chevron = "chevrons-right"
        else:
            self._collapse.setText("Collapse")
            self._collapse.setToolTip("")
            self._collapse.setAccessibleName("Collapse sidebar")
            chevron = "chevrons-left"
        self._collapse.setIcon(icons.render_icon(chevron, pal.text_muted, ICON_SIZE))