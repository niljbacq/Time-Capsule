import re
from dataclasses import fields

import pytest

from session_snapshot.gui import theme

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _linear(channel):
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(color):
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


BOTH = (theme.LIGHT, theme.DARK)


def test_spec_colors_are_exact():
    assert theme.PRIMARY == "#3B82F6"
    assert theme.PRIMARY_HOVER == "#2563EB"
    assert theme.PRIMARY_DARK == "#1D4ED8"
    assert theme.PRIMARY_LIGHT == "#BFDBFE"
    assert theme.SUCCESS == "#16A34A"
    assert theme.WARNING == "#D97706"
    assert theme.ERROR == "#DC2626"
    assert theme.NEUTRAL == "#64748B"


def test_every_palette_value_is_a_hex_color():
    for pal in BOTH:
        for f in fields(theme.Palette):
            assert HEX.match(getattr(pal, f.name)), f.name


def test_light_and_dark_differ_in_surfaces_and_text():
    assert theme.LIGHT.background != theme.DARK.background
    assert theme.LIGHT.surface != theme.DARK.surface
    assert theme.LIGHT.text != theme.DARK.text


def test_primary_and_semantic_colors_match_spec_in_both_modes():
    for pal in BOTH:
        assert pal.primary == theme.PRIMARY
        assert pal.primary_hover == theme.PRIMARY_HOVER
        assert pal.primary_pressed == theme.PRIMARY_DARK
        assert pal.success == theme.SUCCESS
        assert pal.warning == theme.WARNING
        assert pal.error == theme.ERROR
        assert pal.neutral == theme.NEUTRAL


def test_normalize_preference():
    assert theme.normalize_preference("light") == "light"
    assert theme.normalize_preference("dark") == "dark"
    assert theme.normalize_preference("system") == "system"
    assert theme.normalize_preference("purple") == "system"
    assert theme.normalize_preference(None) == "system"
    assert theme.normalize_preference(3) == "system"


def test_resolve_mode_system_follows_desktop():
    assert theme.resolve_mode("system", True) == "dark"
    assert theme.resolve_mode("system", False) == "light"
    assert theme.resolve_mode("garbage", True) == "dark"


def test_resolve_mode_explicit_choice_wins():
    assert theme.resolve_mode("light", True) == "light"
    assert theme.resolve_mode("dark", False) == "dark"


def test_palette_for_modes_and_unknown():
    assert theme.palette_for("light") is theme.LIGHT
    assert theme.palette_for("dark") is theme.DARK
    with pytest.raises(ValueError):
        theme.palette_for("system")


def test_body_text_contrast_is_high():
    for pal in BOTH:
        assert contrast(pal.text, pal.background) >= 7
        assert contrast(pal.text, pal.surface) >= 7


def test_muted_text_meets_aa():
    for pal in BOTH:
        assert contrast(pal.text_muted, pal.surface) >= 4.5
        assert contrast(pal.text_muted, pal.background) >= 4.5


def test_on_primary_is_for_bold_labels_only():
    for pal in BOTH:
        assert contrast(pal.on_primary, pal.primary) >= 3.0


def test_spacing_scale_is_strictly_increasing():
    assert theme.SPACING[0] == 4
    assert list(theme.SPACING) == sorted(set(theme.SPACING))