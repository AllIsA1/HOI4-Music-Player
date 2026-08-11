"""Small GUI helpers: time formatting and icon loading/caching."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageDraw

_icon_cache: dict[tuple[str, int], ctk.CTkImage] = {}
_default_icon_cache: dict[int, ctk.CTkImage] = {}


def format_time(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "--:--"
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


_ICON_BG = (30, 32, 36, 255)
_ICON_FG = (201, 162, 39, 255)


def _make_default_icon(size: int) -> Image.Image:
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 6, fill=_ICON_BG)
    # simple musical-note glyph
    cx, cy = s * 0.42, s * 0.58
    r = s * 0.14
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_ICON_FG)
    stem_w = max(2, s // 16)
    draw.rectangle([cx + r - stem_w, s * 0.18, cx + r, cy], fill=_ICON_FG)
    flag_pts = [
        (cx + r - stem_w, s * 0.18),
        (cx + r + s * 0.16, s * 0.28),
        (cx + r - stem_w, s * 0.38),
    ]
    draw.polygon(flag_pts, fill=_ICON_FG)
    return img.resize((size, size), Image.LANCZOS)


def get_default_icon(size: int) -> ctk.CTkImage:
    cached = _default_icon_cache.get(size)
    if cached is None:
        img = _make_default_icon(size)
        cached = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        _default_icon_cache[size] = cached
    return cached


def get_icon_image(path: Optional[Path], size: int) -> ctk.CTkImage:
    if path is None:
        return get_default_icon(size)
    key = (str(path), size)
    cached = _icon_cache.get(key)
    if cached is not None:
        return cached
    try:
        img = Image.open(path).convert("RGBA")
        img = img.resize((size, size), Image.LANCZOS)
    except Exception:
        return get_default_icon(size)
    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    _icon_cache[key] = ctk_img
    return ctk_img
