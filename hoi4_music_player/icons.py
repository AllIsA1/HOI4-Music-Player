"""Line icons and round controls, drawn with PIL on a 24-unit grid at 4x and
downsampled. Anything round is pre-rendered here because Tk's own canvas
ovals aren't anti-aliased on X11."""
from __future__ import annotations

import math
from typing import Callable

from PIL import Image, ImageDraw, ImageTk

_SS = 4
_photo_cache: dict[tuple, ImageTk.PhotoImage] = {}

Point = tuple[float, float]


class _Pen:
    def __init__(self, draw: ImageDraw.ImageDraw, unit: float, color: str, stroke: float = 1.7):
        self.d = draw
        self.u = unit
        self.color = color
        self.w = max(_SS, stroke * unit)

    def p(self, x: float, y: float) -> Point:
        return (x * self.u, y * self.u)

    def line(self, *points: Point, width: float | None = None) -> None:
        w = self.w if width is None else width * self.u
        pts = [self.p(x, y) for x, y in points]
        self.d.line(pts, fill=self.color, width=int(w), joint="curve")
        r = w / 2
        for x, y in (pts[0], pts[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=self.color)

    def poly(self, *points: Point) -> None:
        self.d.polygon([self.p(x, y) for x, y in points], fill=self.color)

    def rrect(self, x0, y0, x1, y1, r) -> None:
        self.d.rounded_rectangle([*self.p(x0, y0), *self.p(x1, y1)], radius=r * self.u, fill=self.color)

    def arc(self, cx, cy, r, start, end) -> None:
        box = [*self.p(cx - r, cy - r), *self.p(cx + r, cy + r)]
        self.d.arc(box, start=start, end=end, fill=self.color, width=int(self.w))

    def circle(self, cx, cy, r, outline: bool = False) -> None:
        box = [*self.p(cx - r, cy - r), *self.p(cx + r, cy + r)]
        if outline:
            self.d.ellipse(box, outline=self.color, width=int(self.w))
        else:
            self.d.ellipse(box, fill=self.color)


def _play(pen: _Pen) -> None:
    pen.poly((7.5, 4.8), (7.5, 19.2), (19, 12))


def _pause(pen: _Pen) -> None:
    pen.rrect(6.5, 5, 10, 19, 0.8)
    pen.rrect(14, 5, 17.5, 19, 0.8)


def _next(pen: _Pen) -> None:
    pen.poly((5, 5.5), (5, 18.5), (15.5, 12))
    pen.rrect(16.2, 5.5, 18.8, 18.5, 0.6)


def _prev(pen: _Pen) -> None:
    pen.poly((19, 5.5), (19, 18.5), (8.5, 12))
    pen.rrect(5.2, 5.5, 7.8, 18.5, 0.6)


def _shuffle(pen: _Pen) -> None:
    pen.line((3.5, 17), (7.5, 17), (15.5, 7), (19.5, 7))
    pen.line((3.5, 7), (7.5, 7), (10, 10.1))
    pen.line((13.2, 13.9), (15.5, 17), (19.5, 17))
    pen.line((17, 4.5), (19.8, 7), (17, 9.5))
    pen.line((17, 14.5), (19.8, 17), (17, 19.5))


def _repeat(pen: _Pen) -> None:
    pen.line((5, 11.5), (5, 8.5), (6.5, 7), (18.5, 7))
    pen.line((16, 4.5), (18.8, 7), (16, 9.5))
    pen.line((19, 12.5), (19, 15.5), (17.5, 17), (5.5, 17))
    pen.line((8, 14.5), (5.2, 17), (8, 19.5))


def _repeat_one(pen: _Pen) -> None:
    _repeat(pen)
    pen.line((11, 10.6), (12.4, 9.6), (12.4, 14.2), width=1.5)


def _speaker(pen: _Pen) -> None:
    pen.poly((3.5, 9), (7.5, 9), (12, 5), (12, 19), (7.5, 15), (3.5, 15))


def _volume_high(pen: _Pen) -> None:
    _speaker(pen)
    pen.arc(12, 12, 4, -50, 50)
    pen.arc(12, 12, 8, -50, 50)


def _volume_low(pen: _Pen) -> None:
    _speaker(pen)
    pen.arc(12, 12, 4, -50, 50)


def _volume_mute(pen: _Pen) -> None:
    _speaker(pen)
    pen.line((15.5, 9.5), (20.5, 14.5))
    pen.line((20.5, 9.5), (15.5, 14.5))


def _folder(pen: _Pen) -> None:
    pen.line((3.5, 18.5), (3.5, 5.5), (9.5, 5.5), (11.5, 8), (20.5, 8), (20.5, 18.5), (3.5, 18.5))


def _refresh(pen: _Pen) -> None:
    cx, cy, r, end_deg = 12, 12, 7, 320
    pen.arc(cx, cy, r, 35, end_deg)
    a = math.radians(end_deg)
    ex, ey = cx + r * math.cos(a), cy + r * math.sin(a)
    # PIL arcs run clockwise, so travel at the end point is (-sin a, cos a);
    # the arrowhead's arms point back against that direction.
    back = math.atan2(-math.cos(a), math.sin(a))
    arm = 3.6
    pen.line(
        (ex + arm * math.cos(back + 0.75), ey + arm * math.sin(back + 0.75)),
        (ex, ey),
        (ex + arm * math.cos(back - 0.75), ey + arm * math.sin(back - 0.75)),
    )


def _search(pen: _Pen) -> None:
    pen.circle(10.5, 10.5, 6.2, outline=True)
    pen.line((15.2, 15.2), (19.8, 19.8))


def _close(pen: _Pen) -> None:
    pen.line((7, 7), (17, 17))
    pen.line((17, 7), (7, 17))


def _plus(pen: _Pen) -> None:
    pen.line((12, 5.5), (12, 18.5))
    pen.line((5.5, 12), (18.5, 12))


def _eq(pen: _Pen) -> None:
    pen.rrect(4.5, 9, 8, 19, 0.6)
    pen.rrect(10.25, 4.5, 13.75, 19, 0.6)
    pen.rrect(16, 12, 19.5, 19, 0.6)


_GLYPHS: dict[str, Callable[[_Pen], None]] = {
    "play": _play, "pause": _pause, "next": _next, "prev": _prev,
    "shuffle": _shuffle, "repeat": _repeat, "repeat_one": _repeat_one,
    "volume_high": _volume_high, "volume_low": _volume_low, "volume_mute": _volume_mute,
    "folder": _folder, "refresh": _refresh, "search": _search, "close": _close,
    "plus": _plus, "eq": _eq,
}


def glyph_image(name: str, size: int, color: str) -> Image.Image:
    s = size * _SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    _GLYPHS[name](_Pen(ImageDraw.Draw(img), s / 24, color))
    return img.resize((size, size), Image.LANCZOS)


def icon(name: str, size: int, color: str) -> ImageTk.PhotoImage:
    key = ("icon", name, size, color)
    photo = _photo_cache.get(key)
    if photo is None:
        photo = ImageTk.PhotoImage(glyph_image(name, size, color))
        _photo_cache[key] = photo
    return photo


def knob(size: int, fill: str, glyph: str, glyph_color: str) -> ImageTk.PhotoImage:
    """A filled circle with a glyph in it - the main play/pause control."""
    key = ("knob", size, fill, glyph, glyph_color)
    photo = _photo_cache.get(key)
    if photo is None:
        s = size * _SS
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse([0, 0, s - 1, s - 1], fill=fill)
        img = img.resize((size, size), Image.LANCZOS)
        g = glyph_image(glyph, int(size * 0.5), glyph_color)
        offset_x = int(size * 0.03) if glyph == "play" else 0
        img.alpha_composite(g, ((size - g.width) // 2 + offset_x, (size - g.height) // 2))
        photo = ImageTk.PhotoImage(img)
        _photo_cache[key] = photo
    return photo


def dot(size: int, color: str, ring: bool = False, halo: str | None = None) -> ImageTk.PhotoImage:
    """Station on/off lamp: a solid dot (optionally with a soft halo) or a
    hollow ring."""
    key = ("dot", size, color, ring, halo)
    photo = _photo_cache.get(key)
    if photo is None:
        s = size * _SS
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if halo:
            d.ellipse([0, 0, s - 1, s - 1], fill=halo)
        inset = s * 0.25
        box = [inset, inset, s - 1 - inset, s - 1 - inset]
        if ring:
            d.ellipse(box, outline=color, width=max(_SS, int(s * 0.07)))
        else:
            d.ellipse(box, fill=color)
        photo = ImageTk.PhotoImage(img.resize((size, size), Image.LANCZOS))
        _photo_cache[key] = photo
    return photo
