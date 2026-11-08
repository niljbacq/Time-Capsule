import re

from session_snapshot.gui import styles, theme

BOTH = (theme.LIGHT, theme.DARK)
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
TEXT_COLOR = re.compile(r"(?<![-\w])color:\s*(#[0-9A-Fa-f]{6})")
BACKGROUND = re.compile(r"background-color:\s*(#[0-9A-Fa-f]{6})")


def _linear(channel):
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(color):
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def rules(css):
    return [(sel.strip(), body) for sel, body in RULE.findall(css)]


def test_no_unfilled_placeholders():
    for pal in BOTH:
        css = styles.build_stylesheet(pal)
        assert "$" not in css


def test_braces_are_balanced():
    for pal in BOTH:
        css = styles.build_stylesheet(pal)
        assert css.count("{") == css.count("}")
        assert css.count("{") > 20


def test_light_and_dark_differ():
    assert styles.build_stylesheet(theme.LIGHT) != styles.build_stylesheet(theme.DARK)


def test_palette_colors_appear_in_the_output():
    for pal in BOTH:
        css = styles.build_stylesheet(pal).lower()
        for name in (
            "background",
            "surface",
            "border",
            "text",
            "text_muted",
            "primary",
            "primary_hover",
            "primary_pressed",
            "on_primary",
            "active_bg",
            "focus_ring",
            "success",
            "warning",
            "error",
        ):
            assert getattr(pal, name).lower() in css, name


def test_every_object_name_has_a_rule():
    css = styles.build_stylesheet(theme.LIGHT)
    for name in styles.OBJECT_NAMES:
        assert f"#{name}" in css, name


def test_semantic_colors_only_in_status_rules():
    for pal in BOTH:
        for sel, body in rules(styles.build_stylesheet(pal)):
            for color in (theme.SUCCESS, theme.WARNING, theme.ERROR):
                if color.lower() in body.lower():
                    assert "Status" in sel, (sel, color)


def test_primary_blue_only_where_the_spec_allows():
    allowed = ("NavButton", "PrimaryButton", "SecondaryButton")
    for pal in BOTH:
        for sel, body in rules(styles.build_stylesheet(pal)):
            if theme.PRIMARY.lower() in body.lower():
                assert any(name in sel for name in allowed), sel


def test_active_nav_rule_exists():
    css = styles.build_stylesheet(theme.LIGHT)
    assert 'QPushButton#NavButton[active="true"]' in css


def test_font_sizes_and_radius_come_from_the_theme():
    css = styles.build_stylesheet(theme.LIGHT)
    for size in theme.FONT_SIZES.values():
        assert f"{size}px" in css
    assert f"border-radius: {theme.RADIUS}px" in css


def test_only_the_mono_rule_sets_a_font_family():
    css = styles.build_stylesheet(theme.LIGHT)
    assert css.count("font-family") == 1
    assert "font-family: monospace" in css


def test_active_nav_text_has_readable_contrast():
    for pal in BOTH:
        css = styles.build_stylesheet(pal)
        block = next(
            body for sel, body in rules(css) if sel == 'QPushButton#NavButton[active="true"]'
        )
        text = TEXT_COLOR.search(block).group(1)
        background = BACKGROUND.search(block).group(1)
        assert contrast(text, background) >= 4.5


def test_output_is_deterministic():
    assert styles.build_stylesheet(theme.DARK) == styles.build_stylesheet(theme.DARK)