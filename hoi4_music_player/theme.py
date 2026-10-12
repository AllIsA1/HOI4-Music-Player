"""Palette, typography and DPI scaling.

The look is modelled on a 1940s broadcast receiver rather than a generic
dark "app" theme: warm near-black panels, paper-coloured text, and a single
signal-red accent used only for things that are live (the playing track,
the dial needle, enabled stations)."""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

BG = "#11110e"
SURFACE = "#16160f"
PANEL = "#1b1a14"
ROW_ALT = "#1e1d17"
RAISED = "#25241d"
SELECTED = "#2e2c23"
LINE = "#2d2b23"
LINE_STRONG = "#3b382e"

TEXT = "#ebe4d1"
TEXT_2 = "#a8a08b"
TEXT_3 = "#6f695a"
TEXT_4 = "#4a463b"

ACCENT = "#e0502e"
ACCENT_HOVER = "#f0623f"
DANGER = ACCENT

KNOB = "#ebe4d1"
KNOB_HOVER = "#fffaf0"
KNOB_GLYPH = "#16160f"


_scale = 1.0
FONTS: dict[str, tkfont.Font] = {}


def init(root: tk.Misc, families: dict[str, str]) -> None:
    """Must run once, right after the Tk root exists and bundled fonts are
    registered (see fonts.register_bundled_fonts). Everything else sizes
    itself through px() so the layout follows the system DPI setting."""
    global _scale
    points_per_pixel = float(root.tk.call("tk", "scaling"))
    _scale = max(1.0, min(3.0, points_per_pixel * 72 / 96))

    sans, medium, semi, mono = (
        families["sans"], families["sans_medium"], families["sans_semibold"], families["mono"],
    )
    semi_weight = "bold" if semi == sans else "normal"
    medium_weight = "normal"
    spec = {
        "page_title": (semi, 26, semi_weight),
        "brand": (semi, 15, semi_weight),
        "body": (sans, 14, "normal"),
        "body_strong": (semi, 14, semi_weight),
        "row_title": (medium, 14, medium_weight),
        "small": (sans, 12, "normal"),
        "label": (medium, 11, medium_weight),
        "button": (medium, 13, medium_weight),
        "now_title": (semi, 16, semi_weight),
        "mono": (mono, 12, "normal"),
        "mono_small": (mono, 10, "normal"),
        "empty_title": (semi, 20, semi_weight),
    }
    for name, (family, size, weight) in spec.items():
        FONTS[name] = tkfont.Font(root, family=family, size=-px(size), weight=weight)


def px(value: float) -> int:
    return int(round(value * _scale))


_elide_cache: dict[tuple[str, str, int], str] = {}


def elide(text: str, font: tkfont.Font, max_width: int) -> str:
    """Truncates text with an ellipsis so it fits max_width pixels."""
    key = (text, str(font), max_width)
    cached = _elide_cache.get(key)
    if cached is not None:
        return cached
    if font.measure(text) <= max_width:
        result = text
    else:
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if font.measure(text[:mid].rstrip() + "…") <= max_width:
                lo = mid
            else:
                hi = mid - 1
        result = text[:lo].rstrip() + "…" if lo else "…"
    if len(_elide_cache) > 20000:
        _elide_cache.clear()
    _elide_cache[key] = result
    return result


def elide_start(text: str, font: tkfont.Font, max_width: int) -> str:
    """Like elide(), but keeps the end - for file paths, where the last
    folders are the informative part."""
    if font.measure(text) <= max_width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.measure("…" + text[len(text) - mid:].lstrip()) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return "…" + text[len(text) - lo:].lstrip()
