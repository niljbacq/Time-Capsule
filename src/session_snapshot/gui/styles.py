"""Qt style sheet (QSS) text built from a palette. Pure string code, no Qt import."""

from dataclasses import fields
from string import Template

from session_snapshot.gui import theme
from session_snapshot.gui.theme import Palette

# Object names that widgets set with setObjectName() to pick up these rules.
CONTENT = "Content"
SIDEBAR = "Sidebar"
APP_NAME = "AppName"
NAV_BUTTON = "NavButton"
PAGE_TITLE = "PageTitle"
MUTED = "Muted"
MONO = "Mono"
STATUS_SUCCESS = "StatusSuccess"
STATUS_WARNING = "StatusWarning"
STATUS_ERROR = "StatusError"
PRIMARY_BUTTON = "PrimaryButton"
SECONDARY_BUTTON = "SecondaryButton"

OBJECT_NAMES = (
    CONTENT,
    SIDEBAR,
    APP_NAME,
    NAV_BUTTON,
    PAGE_TITLE,
    MUTED,
    MONO,
    STATUS_SUCCESS,
    STATUS_WARNING,
    STATUS_ERROR,
    PRIMARY_BUTTON,
    SECONDARY_BUTTON,
)

_TEMPLATE = Template(
    """\
QMainWindow, QWidget#Content {
    background-color: $background;
}
QWidget {
    color: $text;
    font-size: ${body}px;
}
QToolTip {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
    padding: 4px 8px;
}
QFrame#Sidebar {
    background-color: $surface;
    border-right: 1px solid $border;
}
QLabel#AppName {
    font-size: ${subtitle}px;
    font-weight: 600;
}
QPushButton#NavButton {
    background-color: transparent;
    color: $text;
    border: 2px solid transparent;
    border-radius: ${radius}px;
    padding: 8px 12px;
    text-align: left;
}
QPushButton#NavButton:hover {
    background-color: $border;
}
QPushButton#NavButton[active="true"] {
    background-color: $active_bg;
    color: $active_text;
    font-weight: 600;
}
QPushButton#NavButton:focus {
    border: 2px solid $focus_ring;
}
QLabel#PageTitle {
    font-size: ${title}px;
    font-weight: 600;
}
QLabel#Muted {
    color: $text_muted;
    font-size: ${caption}px;
}
QLabel#Mono {
    font-family: monospace;
}
QLabel#StatusSuccess {
    color: $success;
    font-weight: 600;
}
QLabel#StatusWarning {
    color: $warning;
    font-weight: 600;
}
QLabel#StatusError {
    color: $error;
    font-weight: 600;
}
QPushButton#PrimaryButton {
    background-color: $primary;
    color: $on_primary;
    border: 2px solid transparent;
    border-radius: ${radius}px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background-color: $primary_hover;
}
QPushButton#PrimaryButton:pressed {
    background-color: $primary_pressed;
}
QPushButton#PrimaryButton:focus {
    border: 2px solid $focus_ring;
}
QPushButton#PrimaryButton:disabled {
    background-color: $border;
    color: $text_muted;
}
QPushButton#SecondaryButton {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: ${radius}px;
    padding: 8px 16px;
}
QPushButton#SecondaryButton:hover {
    border-color: $primary;
}
QPushButton#SecondaryButton:focus {
    border: 2px solid $focus_ring;
}
QPushButton#SecondaryButton:disabled {
    color: $text_muted;
}
"""
)


def _active_text(palette: Palette) -> str:
    """Text color for the active nav item, chosen for contrast on active_bg."""
    if palette == theme.LIGHT:
        return theme.PRIMARY_DARK
    if palette == theme.DARK:
        return theme.PRIMARY_LIGHT
    return palette.primary


def build_stylesheet(palette: Palette) -> str:
    """Return the application style sheet for one palette."""
    values: dict[str, object] = {f.name: getattr(palette, f.name) for f in fields(Palette)}
    values["active_text"] = _active_text(palette)
    values["body"] = theme.FONT_SIZES["body"]
    values["caption"] = theme.FONT_SIZES["caption"]
    values["subtitle"] = theme.FONT_SIZES["subtitle"]
    values["title"] = theme.FONT_SIZES["title"]
    values["radius"] = theme.RADIUS
    return _TEMPLATE.substitute(values)