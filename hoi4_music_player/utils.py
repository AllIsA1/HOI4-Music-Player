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
    # Supersample well past the target size, then downsample with LANCZOS -
    # but the stroke widths below are computed in FINAL-size units first and
    # only then scaled up, so they never shrink below ~2 final pixels. That
    # matters more than the supersampling factor: a sub-pixel-wide stroke
    # (e.g. the note stem) looks soft/blurry once resampled down regardless
    # of how much supersampling was used, since there's nothing crisp left
    # to preserve.
    scale = 8 if size <= 32 else 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 6, fill=_ICON_BG)
    # simple musical-note glyph
    cx, cy = s * 0.42, s * 0.58
    r = s * 0.14
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_ICON_FG)
    stem_w = max(2, round(size * 0.09)) * scale
    draw.rectangle([cx + r - stem_w, s * 0.16, cx + r, cy], fill=_ICON_FG)
    flag_pts = [
        (cx + r - stem_w, s * 0.16),
        (cx + r + s * 0.18, s * 0.27),
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


_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def get_app_icon_ico_path() -> Path:
    """Writes a multi-resolution .ico of the app icon to a temp file and
    returns its path, for Tk's Windows-only iconbitmap(). Each size is
    rendered independently (see _make_default_icon) and embedded directly,
    rather than saving one large image and letting the ICO encoder
    downscale it for the smaller sizes - Pillow's own resize for that step
    produced a visibly soft/blurry small icon."""
    tmp_dir = Path(tempfile.gettempdir()) / "hoi4_music_player"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ico_path = tmp_dir / "app_icon.ico"
    images = [_make_default_icon(size) for size in _ICO_SIZES]
    # Pillow's ICO writer skips any requested size larger than the primary
    # image passed to save() - so the primary has to be the LARGEST one
    # (256px) for every other independently-rendered size in append_images
    # to actually get embedded via its exact-size match, instead of being
    # silently dropped.
    images.sort(key=lambda im: im.size)
    images[-1].save(
        ico_path, format="ICO",
        sizes=[(size, size) for size in _ICO_SIZES],
        append_images=images[:-1],
    )
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
