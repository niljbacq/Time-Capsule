import os
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from session_snapshot.gui import icons  # noqa: E402
from session_snapshot.gui.navigation import NAV_ITEMS  # noqa: E402

SVG_TAG = "{http://www.w3.org/2000/svg}svg"
BLUE = "#3B82F6"


@pytest.fixture(scope="session")
def qt_app():
    pytest.importorskip("PySide6.QtSvg")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _icon_image(name, color):
    return icons.render_icon(name, color).pixmap(20, 20).toImage()


def _visible_pixels(image):
    return [
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 0
    ]


def test_every_navigation_icon_exists():
    for item in NAV_ITEMS:
        assert item.icon in icons.ICON_NAMES, item.icon


def test_collapse_chevrons_exist():
    assert "chevrons-left" in icons.ICON_NAMES
    assert "chevrons-right" in icons.ICON_NAMES


def test_every_icon_is_valid_svg():
    for name in icons.ICON_NAMES:
        root = ET.fromstring(icons.svg_text(name, BLUE))
        assert root.tag == SVG_TAG, name


def test_color_is_used_and_current_color_is_not():
    for name in icons.ICON_NAMES:
        text = icons.svg_text(name, BLUE)
        assert f'stroke="{BLUE}"' in text
        assert "currentColor" not in text


def test_unknown_icon_raises_key_error():
    with pytest.raises(KeyError):
        icons.svg_text("nope", BLUE)


def test_bad_colors_are_rejected():
    for bad in ("red", "#FFF", '#3B82F6" onload="x', "", "#GGGGGG"):
        with pytest.raises(ValueError):
            icons.svg_text("layers", bad)


def test_every_icon_renders_visible_pixels(qt_app):
    for name in icons.ICON_NAMES:
        image = _icon_image(name, BLUE)
        assert not image.isNull(), name
        assert _visible_pixels(image), name


def test_color_is_applied_to_rendered_pixels(qt_app):
    red = _icon_image("layers", "#FF0000")
    blue = _icon_image("layers", "#0000FF")
    x, y = max(_visible_pixels(red), key=lambda p: red.pixelColor(*p).alpha())
    a = red.pixelColor(x, y)
    b = blue.pixelColor(x, y)
    assert a.red() > a.blue()
    assert b.blue() > b.red()