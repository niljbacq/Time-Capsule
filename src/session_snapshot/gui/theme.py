"""Design tokens for the GUI: colors, spacing, type sizes. Pure data, no Qt."""

from dataclasses import dataclass
from typing import Literal

ThemeMode = Literal["light", "dark"]
ThemePreference = Literal["system", "light", "dark"]

PREFERENCES: tuple[ThemePreference, ...] = ("system", "light", "dark")
DEFAULT_PREFERENCE: ThemePreference = "system"

# Fixed by the approved design specification.
PRIMARY = "#3B82F6"
PRIMARY_HOVER = "#2563EB"
PRIMARY_DARK = "#1D4ED8"
PRIMARY_LIGHT = "#BFDBFE"
SUCCESS = "#16A34A"
WARNING = "#D97706"
ERROR = "#DC2626"
NEUTRAL = "#64748B"

SPACING = (4, 8, 12, 16, 24, 32)
RADIUS = 6
FONT_SIZES = {"caption": 12, "body": 13, "subtitle": 15, "title": 20}


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str
    border: str
    text: str
    text_muted: str
    primary: str
    primary_hover: str
    primary_pressed: str
    on_primary: str
    active_bg: str
    focus_ring: str
    success: str
    warning: str
    error: str
    neutral: str


LIGHT = Palette(
    background="#F8FAFC",
    surface="#FFFFFF",
    border="#E2E8F0",
    text="#0F172A",
    text_muted="#64748B",
    primary=PRIMARY,
    primary_hover=PRIMARY_HOVER,
    primary_pressed=PRIMARY_DARK,
    on_primary="#FFFFFF",
    active_bg="#EFF6FF",
    focus_ring=PRIMARY_LIGHT,
    success=SUCCESS,
    warning=WARNING,
    error=ERROR,
    neutral=NEUTRAL,
)

DARK = Palette(
    background="#0F172A",
    surface="#1E293B",
    border="#334155",
    text="#F1F5F9",
    text_muted="#94A3B8",
    primary=PRIMARY,
    primary_hover=PRIMARY_HOVER,
    primary_pressed=PRIMARY_DARK,
    on_primary="#FFFFFF",
    active_bg="#1E3A5F",
    focus_ring=PRIMARY,
    success=SUCCESS,
    warning=WARNING,
    error=ERROR,
    neutral=NEUTRAL,
)


def normalize_preference(value: object) -> ThemePreference:
    """Return value if it is a valid preference, else the default (system)."""
    for choice in PREFERENCES:
        if value == choice:
            return choice
    return DEFAULT_PREFERENCE


def resolve_mode(preference: object, system_is_dark: bool) -> ThemeMode:
    """Turn a preference plus the desktop's setting into light or dark."""
    pref = normalize_preference(preference)
    if pref == "system":
        return "dark" if system_is_dark else "light"
    return pref


def palette_for(mode: str) -> Palette:
    if mode == "light":
        return LIGHT
    if mode == "dark":
        return DARK
    raise ValueError(f"unknown theme mode: {mode!r}")