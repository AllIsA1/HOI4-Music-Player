"""Hand-built widgets on plain Tk/ttk, styled from theme.py."""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

from . import icons, theme
from .models import Track
from .theme import px
from .utils import blank_photo, cover_photo, format_time


def setup_styles(root: tk.Misc) -> None:
    style = ttk.Style(root)
    # "clam" is fully Tk-drawn, so it honours the colours below; Windows'
    # native "vista" theme ignores most of them.
    style.theme_use("clam")

    style.layout("Thin.Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"}),
        ]}),
    ])
    style.configure(
        "Thin.Vertical.TScrollbar", width=px(6), arrowsize=px(6), troughcolor=theme.PANEL, background=theme.LINE_STRONG,
        bordercolor=theme.PANEL, lightcolor=theme.LINE_STRONG, darkcolor=theme.LINE_STRONG, gripcount=0,
        relief="flat", borderwidth=0,
    )
    style.map("Thin.Vertical.TScrollbar", background=[("active", theme.TEXT_3)],
              lightcolor=[("active", theme.TEXT_3)], darkcolor=[("active", theme.TEXT_3)])
    style.configure("Sidebar.Thin.Vertical.TScrollbar", troughcolor=theme.SURFACE, bordercolor=theme.SURFACE)

    style.layout("Tracks.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.layout("Tracks.Treeview.Item", [
        ("Treeview.padding", {"sticky": "nswe", "children": [
            ("Treeview.image", {"side": "left", "sticky": ""}),
            ("Treeview.text", {"side": "left", "sticky": ""}),
        ]}),
    ])
    style.configure(
        "Tracks.Treeview", background=theme.PANEL, fieldbackground=theme.PANEL, foreground=theme.TEXT,
        font=theme.FONTS["body"], rowheight=px(36), borderwidth=0, relief="flat",
    )
    style.configure("Tracks.Treeview.Item", padding=(px(12), 0, 0, 0))
    style.map(
        "Tracks.Treeview",
        background=[("selected", theme.SELECTED)],
        foreground=[("selected", theme.TEXT)],
    )
    style.configure(
        "Tracks.Treeview.Heading", background=theme.PANEL, foreground=theme.TEXT_3,
        font=theme.FONTS["label"], relief="flat", borderwidth=0, padding=(px(12), px(8), px(12), px(9)),
        bordercolor=theme.PANEL, lightcolor=theme.PANEL, darkcolor=theme.PANEL,
    )
    style.map("Tracks.Treeview.Heading", background=[("active", theme.PANEL)],
              foreground=[("active", theme.TEXT_2)])


def bind_wheel(widget: tk.Misc, handler: Callable[[int], None]) -> None:
    """handler(steps): negative scrolls up. Covers Windows/macOS
    <MouseWheel> and X11's Button-4/5."""
    widget.bind("<MouseWheel>", lambda e: handler(-1 if e.delta > 0 else 1), add="+")
    widget.bind("<Button-4>", lambda e: handler(-1), add="+")
    widget.bind("<Button-5>", lambda e: handler(1), add="+")


class Tooltip:
    def __init__(self, widget: tk.Widget, text_fn: Callable[[], str]):
        self.widget = widget
        self.text_fn = text_fn
        self._after: Optional[str] = None
        self._tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _e=None):
        self._cancel()
        self._after = self.widget.after(550, self._show)

    def _cancel(self):
        if self._after is not None:
            self.widget.after_cancel(self._after)
            self._after = None

    def _show(self):
        self._after = None
        text = self.text_fn()
        if not text or self._tip is not None:
            return
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.configure(bg=theme.LINE_STRONG)
        tk.Label(
            tip, text=text, bg=theme.RAISED, fg=theme.TEXT, font=theme.FONTS["small"],
            padx=px(8), pady=px(4),
        ).pack(padx=1, pady=1)
        tip.update_idletasks()
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() - tip.winfo_reqwidth()) // 2
        y = self.widget.winfo_rooty() - tip.winfo_reqheight() - px(6)
        tip.geometry(f"+{max(0, x)}+{max(0, y)}")
        self._tip = tip

    def _hide(self, _e=None):
        self._cancel()
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


class FlatButton(tk.Label):
    """Label-based button. Variants: primary (accent fill), secondary
    (raised fill), ghost (no fill until hover), toggle (ghost whose icon
    turns accent while active)."""

    def __init__(
        self, master, text: str = "", icon: Optional[str] = None, variant: str = "ghost",
        command: Optional[Callable[[], None]] = None, bg: str = theme.PANEL, icon_size: int = 16,
        font=None, padx: int = 12, pady: int = 7, tooltip: Optional[Callable[[], str]] = None,
    ):
        self.variant = variant
        self.command = command
        self.icon_name = icon
        self.icon_size = px(icon_size)
        self.active = False
        self._hover = False
        self._base_bg = bg
        super().__init__(
            master, bd=0, highlightthickness=0, cursor="hand2", compound="left",
            font=font or theme.FONTS["button"], padx=px(padx), pady=px(pady),
        )
        self.set_text(text)
        self._apply()
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")
        if tooltip:
            Tooltip(self, tooltip)

    def _colors(self) -> tuple[str, str, str]:
        """(background, text colour, icon colour)"""
        h = self._hover
        if self.variant == "primary":
            bg = theme.ACCENT_HOVER if h else theme.ACCENT
            return bg, "#fff7ee", "#fff7ee"
        if self.variant == "secondary":
            return (theme.SELECTED if h else theme.RAISED), theme.TEXT, theme.TEXT
        if self.variant == "danger":
            return (theme.RAISED if h else self._base_bg), (theme.DANGER if h else theme.TEXT_3), theme.DANGER
        bg = theme.RAISED if h else self._base_bg
        fg = theme.TEXT if h else theme.TEXT_2
        if self.variant == "toggle" and self.active:
            return bg, theme.ACCENT, theme.ACCENT
        return bg, fg, fg

    def _apply(self) -> None:
        bg, fg, icon_color = self._colors()
        image = icons.icon(self.icon_name, self.icon_size, icon_color) if self.icon_name else ""
        self.configure(bg=bg, fg=fg, image=image, activebackground=bg)

    def set_text(self, text: str) -> None:
        # Tk labels have no image/text gap option.
        self.configure(text=("  " + text) if (text and self.icon_name) else text)

    def set_icon(self, name: str) -> None:
        self.icon_name = name
        self._apply()

    def set_active(self, active: bool) -> None:
        self.active = active
        self._apply()

    def _on_enter(self, _e=None):
        self._hover = True
        self._apply()

    def _on_leave(self, _e=None):
        self._hover = False
        self._apply()

    def _on_release(self, e):
        inside = 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()
        if inside and self.command:
            self.command()


class KnobButton(tk.Label):
    """The round play/pause control."""

    def __init__(self, master, size: int, command: Callable[[], None], bg: str):
        super().__init__(master, bd=0, highlightthickness=0, bg=bg, cursor="hand2")
        self.size = px(size)
        self.glyph = "play"
        self._hover = False
        self.command = command
        self._apply()
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_release(self, e):
        if 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self.command()

    def _set_hover(self, hover: bool):
        self._hover = hover
        self._apply()

    def _apply(self):
        fill = theme.KNOB_HOVER if self._hover else theme.KNOB
        self.configure(image=icons.knob(self.size, fill, self.glyph, theme.KNOB_GLYPH))

    def set_glyph(self, glyph: str):
        if glyph != self.glyph:
            self.glyph = glyph
            self._apply()


class SearchBox(tk.Frame):
    def __init__(self, master, variable: tk.StringVar, placeholder: str):
        super().__init__(
            master, bg=theme.BG, highlightthickness=1, highlightbackground=theme.LINE,
            highlightcolor=theme.LINE_STRONG, bd=0,
        )
        self.var = variable
        self.icon = tk.Label(self, image=icons.icon("search", px(16), theme.TEXT_3), bg=theme.BG, bd=0)
        self.icon.pack(side="left", padx=(px(10), px(6)))
        self.entry = tk.Entry(
            self, textvariable=variable, bg=theme.BG, fg=theme.TEXT, insertbackground=theme.TEXT,
            relief="flat", bd=0, highlightthickness=0, font=theme.FONTS["body"],
            selectbackground=theme.SELECTED, selectforeground=theme.TEXT,
        )
        self.entry.pack(side="left", fill="both", expand=True, pady=px(7))
        self.clear = FlatButton(self, icon="close", variant="ghost", bg=theme.BG, command=self._clear,
                                icon_size=14, padx=6, pady=4)
        self.placeholder = tk.Label(
            self.entry, text=placeholder, bg=theme.BG, fg=theme.TEXT_3, font=theme.FONTS["body"], bd=0,
        )
        self.placeholder.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.icon.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<FocusIn>", lambda e: self.configure(highlightbackground=theme.TEXT_3), add="+")
        self.entry.bind("<FocusOut>", lambda e: self.configure(highlightbackground=theme.LINE), add="+")
        variable.trace_add("write", lambda *_: self._sync())
        self._sync()

    def set_placeholder(self, text: str) -> None:
        self.placeholder.configure(text=text)

    def _clear(self) -> None:
        self.var.set("")
        self.entry.focus_set()

    def _sync(self) -> None:
        if self.var.get():
            self.placeholder.place_forget()
            self.clear.pack(side="right", padx=(0, px(4)))
        else:
            self.placeholder.place(x=px(2), rely=0.5, anchor="w")
            self.clear.pack_forget()


class LangSwitch(tk.Frame):
    def __init__(self, master, languages: tuple[str, ...], current: str, on_change: Callable[[str], None], bg: str):
        super().__init__(master, bg=bg)
        self.on_change = on_change
        self.labels: dict[str, tk.Label] = {}
        for code in languages:
            label = tk.Label(self, text=code.upper(), font=theme.FONTS["label"], bd=0, padx=px(7), pady=px(4),
                             cursor="hand2")
            label.pack(side="left")
            label.bind("<Button-1>", lambda e, c=code: self.on_change(c))
            label.bind("<Enter>", lambda e, c=code: self._hover(c, True))
            label.bind("<Leave>", lambda e, c=code: self._hover(c, False))
            self.labels[code] = label
        self._bg = bg
        self.set(current)

    def set(self, current: str) -> None:
        self.current = current
        for code, label in self.labels.items():
            active = code == current
            label.configure(bg=theme.RAISED if active else self._bg, fg=theme.TEXT if active else theme.TEXT_3)

    def _hover(self, code: str, on: bool) -> None:
        if code != self.current:
            self.labels[code].configure(fg=theme.TEXT_2 if on else theme.TEXT_3)


@dataclass
class StationRowData:
    key: Optional[str]
    name: str
    sub: str
    count: str
    enabled: bool = True


class StationList(tk.Frame):
    """Station presets drawn straight onto one canvas, so the list stays a
    single cheap widget no matter how many stations there are. The lamp on
    the left switches a station on/off; the rest of the row selects it."""

    ROW = 50

    def __init__(self, master, on_select, on_toggle, on_activate):
        super().__init__(master, bg=theme.SURFACE)
        self.on_select = on_select
        self.on_toggle = on_toggle
        self.on_activate = on_activate
        self.rows: list[StationRowData] = []
        self.selected_key: Optional[str] = None
        self.live_key: Optional[str] = None
        self._hover: Optional[int] = None
        self._items: list[dict[str, int]] = []
        self.canvas = tk.Canvas(self, bg=theme.SURFACE, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                       style="Sidebar.Thin.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, px(2)))
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._set_hover(None))
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Double-Button-1>", self._on_double)
        bind_wheel(self.canvas, self._on_wheel)

    def set_rows(self, rows: list[StationRowData], selected_key: Optional[str]) -> None:
        self.rows = rows
        self.selected_key = selected_key
        self._redraw()

    def set_selected(self, key: Optional[str]) -> None:
        self.selected_key = key
        for i in range(len(self._items)):
            self._paint(i)

    def set_live(self, key: Optional[str]) -> None:
        """The station currently on air gets the red lamp."""
        if key == self.live_key:
            return
        self.live_key = key
        for i in range(len(self._items)):
            self._paint(i)

    def _index_at(self, y_widget: int) -> Optional[int]:
        y = self.canvas.canvasy(y_widget)
        index = int(y // px(self.ROW))
        return index if 0 <= index < len(self.rows) else None

    def _redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        self._items = []
        width = c.winfo_width()
        if width <= 1:
            return
        h = px(self.ROW)
        name_font, sub_font, count_font = theme.FONTS["row_title"], theme.FONTS["small"], theme.FONTS["mono"]
        text_x = px(40)
        for i, row in enumerate(self.rows):
            y = i * h
            items: dict[str, int] = {}
            items["bg"] = c.create_rectangle(0, y, width, y + h, width=0, fill=theme.SURFACE)
            items["bar"] = c.create_rectangle(0, y + px(12), px(3), y + h - px(12), width=0, fill=theme.ACCENT,
                                              state="hidden")
            if row.key is not None:
                items["lamp"] = c.create_image(px(21), y + h // 2)
            count_w = count_font.measure(row.count)
            c.create_text(width - px(16), y + h // 2, text=row.count, anchor="e", font=count_font,
                          fill=theme.TEXT_3 if row.enabled else theme.TEXT_4)
            max_text = width - text_x - count_w - px(28)
            name_y = y + px(17) if row.sub else y + h // 2
            items["name"] = c.create_text(
                text_x, name_y, anchor="w", font=name_font,
                text=theme.elide(row.name, name_font, max_text),
                fill=theme.TEXT if row.enabled else theme.TEXT_3,
            )
            if row.sub:
                c.create_text(
                    text_x, y + px(34), anchor="w", font=sub_font,
                    text=theme.elide(row.sub, sub_font, max_text),
                    fill=theme.TEXT_2 if row.enabled else theme.TEXT_4,
                )
            if i == 0 and len(self.rows) > 1:
                c.create_line(px(16), y + h - 1, width - px(16), y + h - 1, fill=theme.LINE)
            self._items.append(items)
            self._paint(i)
        total = len(self.rows) * h
        c.configure(scrollregion=(0, 0, width, total))
        if total > c.winfo_height():
            self.scrollbar.grid()
        else:
            self.scrollbar.grid_remove()
            c.yview_moveto(0)

    def _lamp(self, row: StationRowData):
        size = px(18)
        if not row.enabled:
            return icons.dot(size, theme.TEXT_4, ring=True)
        if row.key == self.live_key:
            return icons.dot(size, theme.ACCENT, halo="#40201a")
        return icons.dot(size, theme.TEXT_3)

    def _paint(self, index: int) -> None:
        items = self._items[index]
        row = self.rows[index]
        selected = row.key == self.selected_key
        fill = theme.SELECTED if selected else (theme.RAISED if index == self._hover else theme.SURFACE)
        self.canvas.itemconfigure(items["bg"], fill=fill)
        self.canvas.itemconfigure(items["bar"], state="normal" if selected else "hidden")
        if "lamp" in items:
            self.canvas.itemconfigure(items["lamp"], image=self._lamp(row))

    def _set_hover(self, index: Optional[int]) -> None:
        if index == self._hover:
            return
        previous, self._hover = self._hover, index
        for i in (previous, index):
            if i is not None and i < len(self._items):
                self._paint(i)
        self.canvas.configure(cursor="hand2" if index is not None else "")

    def _on_motion(self, e) -> None:
        self._set_hover(self._index_at(e.y))

    def _on_click(self, e) -> None:
        index = self._index_at(e.y)
        if index is None:
            return
        row = self.rows[index]
        if row.key is not None and e.x < px(36):
            self.on_toggle(row.key, not row.enabled)
        else:
            self.on_select(row.key)

    def _on_double(self, e) -> None:
        index = self._index_at(e.y)
        if index is not None and not (self.rows[index].key is not None and e.x < px(36)):
            self.on_activate(self.rows[index].key)

    def _on_wheel(self, steps: int) -> None:
        if self.scrollbar.winfo_ismapped():
            self.canvas.yview_scroll(steps * 2, "units")


class Dial(tk.Canvas):
    """Seek bar drawn as a tuning scale: a tick per few seconds, a labelled
    major tick per 15s/30s/1min/…, and a red needle. Ticks already played
    are lit; click or drag anywhere on it to seek."""

    HEIGHT = 34

    def __init__(self, master, bg: str, on_drag: Callable[[float], None], on_seek: Callable[[float], None]):
        super().__init__(master, height=px(self.HEIGHT), bg=bg, highlightthickness=0, bd=0)
        self.on_drag = on_drag
        self.on_seek = on_seek
        self.fraction = 0.0
        self.duration: Optional[float] = None
        self.active = False
        self.dragging = False
        self.hover_x: Optional[int] = None
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)

    def _bounds(self) -> tuple[int, int]:
        return px(4), self.winfo_width() - px(4)

    def set_state(self, fraction: float, duration: Optional[float], active: bool) -> None:
        if self.dragging:
            return
        fraction = max(0.0, min(1.0, fraction))
        if (fraction, duration, active) == (self.fraction, self.duration, self.active):
            return
        self.fraction, self.duration, self.active = fraction, duration, active
        self.configure(cursor="hand2" if active else "")
        self.redraw()

    @staticmethod
    def _steps(duration: float, width: int) -> tuple[float, float]:
        """(labelled step, minor step) in seconds, so labels stay ~60px+
        apart and minor ticks ~6px+ apart."""
        major = 600.0
        for candidate in (10, 15, 30, 60, 120, 300, 600):
            if candidate / duration * width >= px(64):
                major = float(candidate)
                break
        minor = major
        for divisions in (10, 6, 5, 3, 2):
            if (major / divisions) / duration * width >= px(6):
                minor = major / divisions
                break
        return major, minor

    def redraw(self) -> None:
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if width <= 1:
            return
        x0, x1 = self._bounds()
        span = x1 - x0
        base = height - px(7)
        needle_x = x0 + span * self.fraction
        lit, unlit = theme.TEXT_2, theme.TEXT_4
        font = theme.FONTS["mono_small"]

        self.create_line(x0, base, x1, base, fill=theme.LINE_STRONG)
        if self.active:
            self.create_line(x0, base, needle_x, base, fill=theme.TEXT_3)

        if self.active and self.duration:
            major, minor = self._steps(self.duration, span)
            count = int(self.duration // minor) + 1
            per_major = round(major / minor)
            for i in range(count):
                t = i * minor
                x = x0 + span * (t / self.duration)
                is_major = i % per_major == 0
                tick = px(9) if is_major else px(4)
                color = lit if x <= needle_x else unlit
                self.create_line(x, base - tick, x, base, fill=color, width=max(1, px(1)))
                if is_major and t > 0 and x1 - x > px(26):
                    minutes, seconds = divmod(int(t), 60)
                    self.create_text(x, base - px(17), text=f"{minutes}:{seconds:02d}", font=font,
                                     fill=theme.TEXT_3 if x <= needle_x else theme.TEXT_4)
        else:
            step = px(8)
            x = x0
            i = 0
            while x <= x1:
                self.create_line(x, base - (px(9) if i % 5 == 0 else px(4)), x, base, fill=unlit)
                x += step
                i += 1

        if self.hover_x is not None and self.active and not self.dragging:
            self.create_line(self.hover_x, px(3), self.hover_x, base, fill=theme.TEXT_3)
        if self.active:
            self.create_rectangle(needle_x - px(1), px(2), needle_x + px(1), base + px(4), width=0, fill=theme.ACCENT)
            self.create_rectangle(needle_x - px(3), px(2), needle_x + px(3), px(4), width=0, fill=theme.ACCENT)

    def _fraction_at(self, x: int) -> float:
        x0, x1 = self._bounds()
        return max(0.0, min(1.0, (x - x0) / max(1, x1 - x0)))

    def _press(self, e):
        if not self.active:
            return
        self.dragging = True
        self._drag(e)

    def _drag(self, e):
        if not self.dragging:
            return
        self.fraction = self._fraction_at(e.x)
        self.redraw()
        self.on_drag(self.fraction)

    def _release(self, e):
        if not self.dragging:
            return
        self.fraction = self._fraction_at(e.x)
        self.dragging = False
        self.redraw()
        self.on_seek(self.fraction)

    def _motion(self, e):
        self.hover_x = e.x
        if self.active and not self.dragging:
            self.redraw()

    def _leave(self, _e):
        self.hover_x = None
        if self.active:
            self.redraw()


class Slider(tk.Canvas):
    def __init__(self, master, width: int, bg: str, value: float, on_change: Callable[[float], None]):
        super().__init__(master, width=px(width), height=px(22), bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.value = value
        self.on_change = on_change
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<ButtonPress-1>", self._set_from_event)
        self.bind("<B1-Motion>", self._set_from_event)
        bind_wheel(self, lambda steps: self.set(self.value - steps * 0.05, notify=True))

    def _bounds(self) -> tuple[int, int]:
        return px(7), self.winfo_width() - px(7)

    def set(self, value: float, notify: bool = False) -> None:
        self.value = max(0.0, min(1.0, value))
        self.redraw()
        if notify:
            self.on_change(self.value)

    def redraw(self) -> None:
        self.delete("all")
        x0, x1 = self._bounds()
        y = self.winfo_height() // 2
        x = x0 + (x1 - x0) * self.value
        self.create_line(x0, y, x1, y, fill=theme.LINE_STRONG, width=px(2))
        self.create_line(x0, y, x, y, fill=theme.TEXT_2, width=px(2))
        self.create_image(x, y, image=icons.dot(px(22), theme.TEXT))

    def _set_from_event(self, e):
        x0, x1 = self._bounds()
        self.set((e.x - x0) / max(1, x1 - x0), notify=True)


class TrackTable(tk.Frame):
    """Track list on a native ttk.Treeview. A widget-per-row list froze the
    app on real 2000-3000 track libraries; Treeview only draws the visible
    rows."""

    ART = 22

    def __init__(self, master, on_play: Callable[[Track], None], headings: dict[str, str]):
        super().__init__(master, bg=theme.PANEL)
        self.on_play = on_play
        self.tracks: list[Track] = []
        self._path_to_iid: dict[Path, str] = {}
        self._playing_iid: Optional[str] = None
        self._raw: list[tuple[str, str, str, str]] = []
        self._widths: dict[str, int] = {}
        self._reelide_after: Optional[str] = None
        self.single_station = False
        self.unknown_author = ""

        columns = ("author", "station", "mod", "time")
        self.tree = ttk.Treeview(self, columns=columns, show="tree headings", style="Tracks.Treeview",
                                 selectmode="browse", takefocus=True)
        for column, anchor in (("#0", "w"), ("author", "w"), ("station", "w"), ("mod", "w"), ("time", "e")):
            self.tree.column(column, anchor=anchor, stretch=False, minwidth=px(40))
        self.tree.tag_configure("odd", background=theme.ROW_ALT)
        self.tree.tag_configure("playing", foreground=theme.ACCENT)
        self._display: tuple[str, ...] = ()
        self.set_headings(headings)

        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview,
                                       style="Thin.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(px(6), px(4)))
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-Button-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_enter_key)
        self.tree.bind("<Configure>", self._fit_columns)

    def _fit_columns(self, _event=None) -> None:
        """Columns share the width by fixed proportions (Treeview's own
        stretch logic lets the last columns run off-screen), and the Mod
        column steps aside when the window gets narrow."""
        width = self.tree.winfo_width()
        if width <= 1:
            return
        time_w = px(78)
        if self.single_station:
            # Every row would repeat the same station and mod.
            display = ("author", "time")
            shares = {"#0": 0.6, "author": 0.4, "station": 0.0, "mod": 0.0}
        elif width >= px(760):
            display = ("author", "station", "mod", "time")
            shares = {"#0": 0.39, "author": 0.21, "station": 0.18, "mod": 0.22}
        else:
            display = ("author", "station", "time")
            shares = {"#0": 0.48, "author": 0.27, "station": 0.25, "mod": 0.0}
        if display != self._display:
            self._display = display
            self.tree.configure(displaycolumns=display)
        rest = width - time_w
        widths = {column: max(px(40), int(rest * share)) for column, share in shares.items()}
        for column, w in widths.items():
            self.tree.column(column, width=w)
        self.tree.column("time", width=time_w)
        if widths != self._widths:
            self._widths = widths
            if self._reelide_after is not None:
                self.after_cancel(self._reelide_after)
            self._reelide_after = self.after(120, self._reelide)

    def _cells(self, raw: tuple[str, str, str, str]) -> tuple[str, tuple[str, str, str]]:
        """Treeview clips overflowing text mid-glyph, so cut it with an
        ellipsis to the current column widths instead."""
        font = theme.FONTS["body"]
        title, author, station, mod = raw
        w = self._widths
        if not w:
            return "  " + title, ("  " + author, "  " + station, "  " + mod)
        gap = font.measure("  ")
        title_room = w["#0"] - px(self.ART) - px(12) - gap - px(10)
        cell = lambda text, col: "  " + theme.elide(text, font, max(px(20), w[col] - gap - px(12)))
        return "  " + theme.elide(title, font, max(px(20), title_room)), (
            cell(author, "author"), cell(station, "station"), cell(mod, "mod"),
        )

    def _reelide(self) -> None:
        self._reelide_after = None
        for i, raw in enumerate(self._raw):
            text, (author, station, mod) = self._cells(raw)
            iid = str(i)
            self.tree.item(iid, text=text)
            self.tree.set(iid, "author", author)
            self.tree.set(iid, "station", station)
            self.tree.set(iid, "mod", mod)

    def set_headings(self, headings: dict[str, str]) -> None:
        # Indent the title heading past the rows' cover column so it lines up
        # with the titles (a heading image would be drawn on the right).
        indent = px(self.ART) + theme.FONTS["body"].measure("  ")
        spaces = round(indent / max(1, theme.FONTS["label"].measure(" ")))
        self.tree.heading("#0", text=" " * spaces + headings["title"].upper(), anchor="w")
        self.tree.heading("author", text=headings["author"].upper(), anchor="w")
        self.tree.heading("station", text=headings["station"].upper(), anchor="w")
        self.tree.heading("mod", text=headings["mod"].upper(), anchor="w")
        self.tree.heading("time", text=headings["time"].upper() + "  ", anchor="e")

    def _art(self, track: Track):
        # Only per-track covers: the mod's own icon repeated on every row of
        # that mod is just noise (it's shown in the player bar instead).
        if track.track_icon is None:
            return blank_photo(px(self.ART))
        return cover_photo(track.track_icon, px(self.ART), radius=px(3))

    @staticmethod
    def _time(track: Track) -> str:
        return format_time(track.duration) + "  "

    def set_tracks(self, tracks: list[Track], playing_path: Optional[Path], single_station: bool = False) -> None:
        if single_station != self.single_station:
            self.single_station = single_station
            self._fit_columns()
        self.tree.delete(*self.tree.get_children())
        self.tracks = tracks
        self._path_to_iid = {}
        self._playing_iid = None
        self._raw = [
            (tr.track_title, tr.track_author or self.unknown_author, tr.station_name, tr.mod_name) for tr in tracks
        ]
        for i, track in enumerate(tracks):
            iid = str(i)
            text, values = self._cells(self._raw[i])
            self.tree.insert(
                "", "end", iid=iid, text=text, image=self._art(track),
                values=(*values, self._time(track)),
                tags=("odd",) if i % 2 else (),
            )
            self._path_to_iid[track.file_path] = iid
        self.set_playing(playing_path, scroll=True)

    def set_playing(self, playing_path: Optional[Path], scroll: bool = True) -> None:
        previous = self._playing_iid
        if previous is not None and self.tree.exists(previous):
            index = int(previous)
            tags = [t for t in self.tree.item(previous, "tags") if t != "playing"]
            self.tree.item(previous, tags=tuple(tags), image=self._art(self.tracks[index]))
        self._playing_iid = None
        if playing_path is None:
            return
        iid = self._path_to_iid.get(playing_path)
        if iid is None:
            return
        tags = list(self.tree.item(iid, "tags")) + ["playing"]
        self.tree.item(iid, tags=tuple(tags), image=icons.icon("eq", px(self.ART), theme.ACCENT))
        self._playing_iid = iid
        if scroll:
            self.tree.see(iid)

    def reveal_playing(self) -> None:
        if self._playing_iid is not None:
            self.tree.see(self._playing_iid)
            self.tree.selection_set(self._playing_iid)

    def update_track_duration(self, track: Track) -> None:
        iid = self._path_to_iid.get(track.file_path)
        if iid is not None:
            self.tree.set(iid, "time", self._time(track))

    def _on_double_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "heading":
            return
        iid = self.tree.identify_row(event.y)
        if iid:
            self._play_iid(iid)

    def _on_enter_key(self, _event):
        selection = self.tree.selection()
        if selection:
            self._play_iid(selection[0])

    def _play_iid(self, iid: str):
        index = int(iid)
        if 0 <= index < len(self.tracks):
            self.on_play(self.tracks[index])
