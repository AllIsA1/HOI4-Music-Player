"""Procedurally drawn, anti-aliased vector-style icons for player controls.
Drawn at 4x scale and downsampled so edges stay smooth at any target size,
instead of relying on font/emoji glyphs that render inconsistently across
operating systems."""
from __future__ import annotations

import math
from typing import Callable

import customtkinter as ctk
from PIL import Image, ImageDraw

_SUPERSAMPLE = 4
_cache: dict[tuple, ctk.CTkImage] = {}


def _render(name: str, size: int, color: str, draw_fn: Callable[[ImageDraw.ImageDraw, float, str], None]) -> ctk.CTkImage:
    key = (name, size, color)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    s = size * _SUPERSAMPLE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_fn(draw, s, color)
    img = img.resize((size, size), Image.LANCZOS)
    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    _cache[key] = ctk_img
    return ctk_img


def _play(draw, s, color):
    m = s * 0.24
    draw.polygon([(m, s * 0.14), (m, s * 0.86), (s * 0.86, s * 0.5)], fill=color)


def _pause(draw, s, color):
    bar_w = s * 0.20
    gap = s * 0.14
    x0 = s * 0.5 - gap / 2 - bar_w
    x1 = s * 0.5 + gap / 2
    r = bar_w * 0.35
    draw.rounded_rectangle([x0, s * 0.15, x0 + bar_w, s * 0.85], radius=r, fill=color)
    draw.rounded_rectangle([x1, s * 0.15, x1 + bar_w, s * 0.85], radius=r, fill=color)


def _skip(draw, s, color, flip: bool):
    def pts(x):
        tri = [(x, s * 0.18), (x, s * 0.82), (x + s * 0.30, s * 0.5)]
        return tri

    triangle = pts(s * 0.16)
    bar = [s * 0.68, s * 0.16, s * 0.78, s * 0.84]
    if flip:
        triangle = [(s - x, y) for x, y in triangle]
        bar = [s - bar[2], bar[1], s - bar[0], bar[3]]
    draw.polygon(triangle, fill=color)
    draw.rounded_rectangle(bar, radius=s * 0.02, fill=color)


def _next(draw, s, color):
    _skip(draw, s, color, flip=False)


def _previous(draw, s, color):
    _skip(draw, s, color, flip=True)


def _shuffle(draw, s, color):
    lw = max(2, int(s * 0.08))

    path_down = [(s * 0.12, s * 0.28), (s * 0.42, s * 0.28), (s * 0.88, s * 0.76)]
    path_up = [(s * 0.12, s * 0.76), (s * 0.42, s * 0.76), (s * 0.88, s * 0.28)]
    draw.line(path_down, fill=color, width=lw, joint="curve")
    draw.line(path_up, fill=color, width=lw, joint="curve")

    def arrowhead(tip, tail):
        ang = math.atan2(tip[1] - tail[1], tip[0] - tail[0])
        head = s * 0.16
        for da in (0.5, -0.5):
            hx = tip[0] - head * math.cos(ang - da)
            hy = tip[1] - head * math.sin(ang - da)
            draw.line([tip, (hx, hy)], fill=color, width=lw)

    arrowhead(path_down[-1], path_down[-2])
    arrowhead(path_up[-1], path_up[-2])


def _repeat_arc(draw, s, color, badge: str = ""):
    cx, cy, r = s * 0.5, s * 0.48, s * 0.30
    width = max(2, int(s * 0.10))
    draw.arc([cx - r, cy - r, cx + r, cy + r], start=20, end=290, fill=color, width=width)
    ang = math.radians(290)
    ax, ay = cx + r * math.cos(ang), cy + r * math.sin(ang)
    head = s * 0.15
    tangent = ang - math.pi / 2
    for da in (0.55, -0.55):
        hx = ax - head * math.cos(tangent - da)
        hy = ay - head * math.sin(tangent - da)
        draw.line([(ax, ay), (hx, hy)], fill=color, width=width)
    if badge:
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("arial.ttf", int(s * 0.36))
        except Exception:
            font = None
        bbox = draw.textbbox((0, 0), badge, font=font) if font else (0, 0, s * 0.2, s * 0.3)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1] - s * 0.02), badge, fill=color, font=font)


def _volume(draw, s, color):
    body = [(s * 0.14, s * 0.38), (s * 0.32, s * 0.38), (s * 0.52, s * 0.20), (s * 0.52, s * 0.80), (s * 0.32, s * 0.62), (s * 0.14, s * 0.62)]
    draw.polygon(body, fill=color)
    lw = max(2, int(s * 0.06))
    draw.arc([s * 0.56, s * 0.32, s * 0.74, s * 0.68], start=-55, end=55, fill=color, width=lw)
    draw.arc([s * 0.62, s * 0.20, s * 0.88, s * 0.80], start=-50, end=50, fill=color, width=lw)


def _folder(draw, s, color):
    pts = [
        (s * 0.12, s * 0.26),
        (s * 0.40, s * 0.26),
        (s * 0.48, s * 0.36),
        (s * 0.88, s * 0.36),
        (s * 0.88, s * 0.80),
        (s * 0.12, s * 0.80),
    ]
    draw.polygon(pts, fill=color)


def _refresh(draw, s, color):
    cx, cy, r = s * 0.5, s * 0.5, s * 0.32
    width = max(2, int(s * 0.10))
    draw.arc([cx - r, cy - r, cx + r, cy + r], start=-200, end=160, fill=color, width=width)
    ang = math.radians(160)
    ax, ay = cx + r * math.cos(ang), cy + r * math.sin(ang)
    head = s * 0.16
    tangent = ang - math.pi / 2
    for da in (0.55, -0.55):
        hx = ax - head * math.cos(tangent - da)
        hy = ay - head * math.sin(tangent - da)
        draw.line([(ax, ay), (hx, hy)], fill=color, width=width)


def _search(draw, s, color):
    lw = max(2, int(s * 0.09))
    draw.ellipse([s * 0.14, s * 0.14, s * 0.62, s * 0.62], outline=color, width=lw)
    draw.line([(s * 0.56, s * 0.56), (s * 0.86, s * 0.86)], fill=color, width=lw)


def play_icon(size=22, color="#ffffff"):
    return _render("play", size, color, _play)


def pause_icon(size=22, color="#ffffff"):
    return _render("pause", size, color, _pause)


def next_icon(size=22, color="#ffffff"):
    return _render("next", size, color, _next)


def previous_icon(size=22, color="#ffffff"):
    return _render("previous", size, color, _previous)


def shuffle_icon(size=22, color="#ffffff"):
    return _render("shuffle", size, color, _shuffle)


def repeat_icon(size=22, color="#ffffff", mode: str = "all"):
    badge = "1" if mode == "one" else ""
    return _render(f"repeat_{mode}", size, color, lambda d, s, c: _repeat_arc(d, s, c, badge))


def volume_icon(size=20, color="#ffffff"):
    return _render("volume", size, color, _volume)


def folder_icon(size=18, color="#ffffff"):
    return _render("folder", size, color, _folder)


def refresh_icon(size=18, color="#ffffff"):
    return _render("refresh", size, color, _refresh)


def search_icon(size=16, color="#ffffff"):
    return _render("search", size, color, _search)
