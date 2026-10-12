"""Time formatting, cover art loading and the app-icon files Tk needs."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageTk

from .brand import app_icon

_cover_cache: dict[tuple[Optional[str], int, int], ImageTk.PhotoImage] = {}


def format_time(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "–:––"
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def _placeholder_cover(size: int) -> Image.Image:
    """A dark shellac record, for tracks and mods with no art of their own."""
    ss = 4
    s = size * ss
    img = Image.new("RGBA", (s, s), (37, 35, 28, 255))
    d = ImageDraw.Draw(img)
    c = s / 2
    d.ellipse([c - s * 0.40, c - s * 0.40, c + s * 0.40, c + s * 0.40], fill=(22, 21, 17, 255))
    for r in (0.34, 0.27, 0.20):
        d.ellipse([c - s * r, c - s * r, c + s * r, c + s * r], outline=(44, 42, 34, 255), width=max(1, s // 64))
    d.ellipse([c - s * 0.11, c - s * 0.11, c + s * 0.11, c + s * 0.11], fill=(122, 52, 33, 255))
    d.ellipse([c - s * 0.025, c - s * 0.025, c + s * 0.025, c + s * 0.025], fill=(22, 21, 17, 255))
    return img.resize((size, size), Image.LANCZOS)


def _round(img: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return img
    ss = 4
    mask = Image.new("L", (img.width * ss, img.height * ss), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, mask.width - 1, mask.height - 1], radius=radius * ss, fill=255)
    out = img.copy()
    out.putalpha(mask.resize(img.size, Image.LANCZOS))
    return out


def cover_photo(path: Optional[Path], size: int, radius: int = 0) -> ImageTk.PhotoImage:
    key = (str(path) if path is not None else None, size, radius)
    photo = _cover_cache.get(key)
    if photo is not None:
        return photo
    img = None
    if path is not None:
        try:
            with Image.open(path) as src:
                img = src.convert("RGBA").resize((size, size), Image.LANCZOS)
        except Exception:
            img = None
    if img is None:
        img = _placeholder_cover(size)
    photo = ImageTk.PhotoImage(_round(img, radius))
    _cover_cache[key] = photo
    return photo


def blank_photo(size: int) -> ImageTk.PhotoImage:
    key = ("blank", size, 0)
    photo = _cover_cache.get(key)
    if photo is None:
        photo = ImageTk.PhotoImage(Image.new("RGBA", (size, size), (0, 0, 0, 0)))
        _cover_cache[key] = photo
    return photo


_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def write_ico(path: Path) -> Path:
    """Multi-size .ico with every size rendered on its own (Pillow's ICO
    writer would otherwise downscale one big image, which looks soft)."""
    images = sorted((app_icon(size) for size in _ICO_SIZES), key=lambda im: im.size)
    # The ICO writer drops any size larger than the primary image, so the
    # largest one has to be the primary.
    images[-1].save(path, format="ICO", sizes=[(s, s) for s in _ICO_SIZES], append_images=images[:-1])
    return path


def temp_ico_path() -> Path:
    tmp_dir = Path(tempfile.gettempdir()) / "hoi4_music_player"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return write_ico(tmp_dir / "app_icon.ico")
