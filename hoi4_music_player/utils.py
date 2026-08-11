"""Small GUI helpers: time formatting and icon loading/caching."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

_icon_cache: dict[tuple[str, int], ctk.CTkImage] = {}
_default_icon_cache: dict[int, ctk.CTkImage] = {}
_icon_photo_cache: dict[tuple[Optional[str], int], ImageTk.PhotoImage] = {}


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


def get_app_icon_image(size: int = 64) -> Image.Image:
    """The app's note-glyph icon as a plain PIL image (not a CTkImage), for
    use as the window/taskbar icon via Tk's iconphoto/iconbitmap - it's
    generated in-process rather than loaded from a bundled file, so the
    packaged .exe doesn't need any asset files shipped alongside it."""
    return _make_default_icon(size)


def get_app_icon_ico_path() -> Path:
    """Writes (once per run) a multi-resolution .ico of the app icon to a
    temp file and returns its path, for Tk's Windows-only iconbitmap()."""
    tmp_dir = Path(tempfile.gettempdir()) / "hoi4_music_player"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ico_path = tmp_dir / "app_icon.ico"
    if not ico_path.exists():
        img = _make_default_icon(256)
        img.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico_path


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


def get_icon_photo(path: Optional[Path], size: int) -> ImageTk.PhotoImage:
    """Same as get_icon_image, but as a plain Tk PhotoImage - needed for
    widgets that don't understand CTkImage, like ttk.Treeview row icons."""
    key = (str(path) if path is not None else None, size)
    cached = _icon_photo_cache.get(key)
    if cached is not None:
        return cached
    img = None
    if path is not None:
        try:
            img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        except Exception:
            img = None
    if img is None:
        img = _make_default_icon(size)
    photo = ImageTk.PhotoImage(img)
    _icon_photo_cache[key] = photo
    return photo
