"""Outline icons in the Lucide style, drawn as small SVGs. No network, no icon font.

svg_text() is pure string code. render_icon() needs PySide6 and a running
QGuiApplication; it imports Qt only when called.
"""

import re

_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")

_BODIES: dict[str, str] = {
    "layout-dashboard": (
        '<rect x="3" y="3" width="7" height="9" rx="1"/>'
        '<rect x="14" y="3" width="7" height="5" rx="1"/>'
        '<rect x="14" y="12" width="7" height="9" rx="1"/>'
        '<rect x="3" y="16" width="7" height="5" rx="1"/>'
    ),
    "layers": (
        '<path d="M12 3L21 8L12 13L3 8Z"/>'
        '<path d="M3 12L12 17L21 12"/>'
        '<path d="M3 16L12 21L21 16"/>'
    ),
    "puzzle": '<path d="M4 8h4a2 2 0 1 1 4 0h8v12H4Z"/>',
    "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    "settings": (
        '<path d="M4 6h3"/><circle cx="9.5" cy="6" r="2"/><path d="M11.5 6H20"/>'
        '<path d="M4 12h8"/><circle cx="14.5" cy="12" r="2"/><path d="M16.5 12H20"/>'
        '<path d="M4 18h2"/><circle cx="8.5" cy="18" r="2"/><path d="M10.5 18H20"/>'
    ),
    "chevrons-left": (
        '<polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/>'
    ),
    "chevrons-right": (
        '<polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/>'
    ),
}

ICON_NAMES: tuple[str, ...] = tuple(_BODIES)


def svg_text(name: str, color: str) -> str:
    """Return the SVG source for one icon in one color (#RRGGBB)."""
    if name not in _BODIES:
        raise KeyError(name)
    if not _COLOR.match(color):
        raise ValueError(f"icon color must look like #RRGGBB, got {color!r}")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="24" height="24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{_BODIES[name]}</svg>"
    )


def render_icon(name: str, color: str, size: int = 20):
    """Render an icon to a QIcon at the given logical size (drawn at 2x)."""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg_text(name, color).encode("utf-8")))
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)