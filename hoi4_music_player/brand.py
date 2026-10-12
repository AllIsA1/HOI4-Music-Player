"""The app icon: a bakelite radio set with a lit tuning dial. Drawn in code
so the window icon, the .ico/.png assets (packaging/make_icons.py) and the
in-app logo always match."""
from __future__ import annotations

from PIL import Image, ImageDraw

BODY_TOP = (46, 40, 31)
BODY_BOTTOM = (24, 21, 16)
DIAL_TOP = (247, 225, 172)
DIAL_BOTTOM = (226, 172, 88)
TICK = (92, 62, 28)
NEEDLE = (206, 58, 32)
GRILLE = (64, 56, 44)


def _vertical_gradient(size: tuple[int, int], top, bottom) -> Image.Image:
    w, h = size
    column = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        column.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return column.resize((w, h))


def _mask(size: tuple[int, int], box, radius: float) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    return mask


def app_icon(size: int) -> Image.Image:
    small = size <= 32
    ss = 8 if size <= 64 else 4
    s = size * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    body_box = [0, 0, s - 1, s - 1]
    img.paste(_vertical_gradient((s, s), BODY_TOP, BODY_BOTTOM), (0, 0), _mask((s, s), body_box, s * 0.22))
    draw = ImageDraw.Draw(img)
    if not small:
        draw.rounded_rectangle(body_box, radius=s * 0.22, outline=(255, 244, 220, 28), width=max(1, s // 128))

    if small:
        win = [s * 0.13, s * 0.14, s * 0.87, s * 0.60]
    else:
        win = [s * 0.14, s * 0.15, s * 0.86, s * 0.56]
    win = [round(v) for v in win]
    win_w, win_h = win[2] - win[0], win[3] - win[1]
    dial = _vertical_gradient((win_w, win_h), DIAL_TOP, DIAL_BOTTOM)
    img.paste(dial, (win[0], win[1]), _mask((win_w, win_h), [0, 0, win_w - 1, win_h - 1], s * 0.06))

    if small:
        if size > 24:
            for x in (0.30, 0.50, 0.70):
                draw.rectangle([s * x - s * 0.025, s * 0.44, s * x + s * 0.025, s * 0.53], fill=TICK)
        nx, nw = s * 0.60, s * 0.085
        draw.rectangle([nx - nw / 2, s * 0.17, nx + nw / 2, s * 0.57], fill=NEEDLE)
        for y in (0.71, 0.84):
            draw.rounded_rectangle([s * 0.24, s * y - s * 0.045, s * 0.76, s * y + s * 0.045], radius=s * 0.045, fill=GRILLE)
    else:
        base = s * 0.47
        left, right, count = s * 0.22, s * 0.78, 17
        for i in range(count):
            x = left + (right - left) * i / (count - 1)
            major = i % 4 == 0
            h = s * (0.10 if major else 0.05)
            w = s * (0.016 if major else 0.010)
            draw.rectangle([x - w / 2, base - h, x + w / 2, base], fill=TICK)
        draw.rectangle([left, base, right, base + s * 0.010], fill=TICK)
        nx, nw = s * 0.615, s * 0.034
        draw.rectangle([nx - nw / 2, s * 0.19, nx + nw / 2, s * 0.53], fill=NEEDLE)
        for y in (0.67, 0.755, 0.84):
            draw.rounded_rectangle([s * 0.24, s * y - s * 0.022, s * 0.76, s * y + s * 0.022], radius=s * 0.022, fill=GRILLE)

    return img.resize((size, size), Image.LANCZOS)
