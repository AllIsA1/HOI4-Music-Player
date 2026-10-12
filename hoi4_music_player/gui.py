"""Main window of the HOI4 Music Player (plain Tk/ttk, see widgets.py)."""
from __future__ import annotations

import ctypes
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Optional

from PIL import ImageTk

from . import fonts, i18n, icons, theme
from .brand import app_icon
from .config import Config
from .duration import compute_track_duration
from .i18n import t
from .mod_scanner import scan_folders_detailed
from .models import Station, Track
from .player_engine import PlayerEngine, RepeatMode
from .theme import px
from .utils import cover_photo, format_time, temp_ico_path
from .widgets import (
    Dial,
    FlatButton,
    KnobButton,
    LangSwitch,
    SearchBox,
    Slider,
    StationList,
    StationRowData,
    TrackTable,
    setup_styles,
)

SIDEBAR_WIDTH = 288
TOOLBAR_HEIGHT = 64
COVER_SIZE = 48


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _dark_title_bar(window: tk.Misc) -> None:
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE; 19 on Windows 10 builds before 20H1.
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            ) == 0:
                break
    except Exception:
        pass


def _style_stock_widgets(root: tk.Tk) -> None:
    """Dark colours for stock widgets we don't build ourselves - mostly Tk's
    own file dialog on Linux."""
    root.tk_setPalette(
        background=theme.BG, foreground=theme.TEXT, activeBackground=theme.RAISED,
        activeForeground=theme.TEXT, highlightColor=theme.LINE_STRONG, highlightBackground=theme.BG,
        selectBackground=theme.SELECTED, selectForeground=theme.TEXT, insertBackground=theme.TEXT,
        troughColor=theme.PANEL, disabledForeground=theme.TEXT_3,
    )
    style = ttk.Style(root)
    style.configure(".", background=theme.BG, foreground=theme.TEXT, fieldbackground=theme.PANEL,
                    bordercolor=theme.LINE, lightcolor=theme.RAISED, darkcolor=theme.RAISED,
                    troughcolor=theme.PANEL, selectbackground=theme.SELECTED, selectforeground=theme.TEXT,
                    insertcolor=theme.TEXT, arrowcolor=theme.TEXT_2, focuscolor=theme.LINE_STRONG,
                    font=theme.FONTS["small"])
    style.configure("TButton", background=theme.RAISED, padding=(px(10), px(4)))
    style.map("TButton", background=[("active", theme.SELECTED)])
    style.map("TCombobox", fieldbackground=[("readonly", theme.PANEL)],
              background=[("active", theme.RAISED)], foreground=[("readonly", theme.TEXT)])


class EmptyState(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=theme.PANEL)
        inner = tk.Frame(self, bg=theme.PANEL)
        inner.place(relx=0.5, rely=0.4, anchor="center")
        tk.Label(inner, image=cover_photo(None, px(72), radius=px(8)), bg=theme.PANEL).pack(pady=(0, px(18)))
        self.title = tk.Label(inner, font=theme.FONTS["empty_title"], fg=theme.TEXT, bg=theme.PANEL)
        self.title.pack()
        self.body = tk.Label(inner, font=theme.FONTS["body"], fg=theme.TEXT_2, bg=theme.PANEL,
                             wraplength=px(440), justify="center")
        self.body.pack(pady=(px(6), 0))
        self.actions = tk.Frame(inner, bg=theme.PANEL)
        self.actions.pack(pady=(px(20), 0))

    def show(self, title: str, body: str = "", action: Optional[tuple[str, str, object]] = None) -> None:
        self.title.configure(text=title)
        self.body.configure(text=body)
        if body:
            self.body.pack(pady=(px(6), 0), before=self.actions)
        else:
            self.body.pack_forget()
        for child in self.actions.winfo_children():
            child.destroy()
        if action:
            text, variant, command = action
            icon = "plus" if variant == "primary" else None
            FlatButton(self.actions, text=text, icon=icon, variant=variant, command=command,
                       bg=theme.PANEL, padx=16, pady=8).pack()


class FoldersDialog(tk.Toplevel):
    def __init__(self, app: "App"):
        super().__init__(app)
        self.app = app
        lang = app.lang
        self.title(t(lang, "folders_title"))
        self.configure(bg=theme.BG)
        self.geometry(f"{px(640)}x{px(430)}")
        self.minsize(px(460), px(320))
        self.transient(app)
        _dark_title_bar(self)

        pad = px(26)
        tk.Label(self, text=t(lang, "folders_title"), font=theme.FONTS["empty_title"], fg=theme.TEXT,
                 bg=theme.BG, anchor="w").pack(fill="x", padx=pad, pady=(pad, px(2)))
        tk.Label(self, text=t(lang, "folders_body"), font=theme.FONTS["body"], fg=theme.TEXT_2, bg=theme.BG,
                 anchor="w", justify="left").pack(fill="x", padx=pad)

        self.list = tk.Frame(self, bg=theme.PANEL, highlightthickness=1, highlightbackground=theme.LINE)
        self.list.pack(fill="both", expand=True, padx=pad, pady=px(18))

        footer = tk.Frame(self, bg=theme.BG)
        footer.pack(fill="x", padx=pad, pady=(0, pad))
        FlatButton(footer, text=t(lang, "add_folder"), icon="plus", variant="secondary", bg=theme.BG,
                   command=self._add, padx=14, pady=8).pack(side="left")
        FlatButton(footer, text=t(lang, "done"), variant="primary", bg=theme.BG,
                   command=self.destroy, padx=20, pady=8).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        self._render()
        self.focus_set()

    def _render(self) -> None:
        for child in self.list.winfo_children():
            child.destroy()
        lang = self.app.lang
        folders = self.app.config_store.folders
        if not folders:
            tk.Label(self.list, text=t(lang, "no_folders_yet"), font=theme.FONTS["body"], fg=theme.TEXT_3,
                     bg=theme.PANEL, anchor="w").pack(fill="x", padx=px(16), pady=px(16))
            return
        for i, folder in enumerate(folders):
            if i:
                tk.Frame(self.list, bg=theme.LINE, height=1).pack(fill="x", padx=px(12))
            row = tk.Frame(self.list, bg=theme.PANEL)
            row.pack(fill="x", padx=px(6), pady=px(4))
            FlatButton(row, text=t(lang, "remove"), variant="danger", bg=theme.PANEL, padx=10, pady=5,
                       command=lambda f=folder: self._remove(f)).pack(side="right")
            tk.Label(row, image=icons.icon("folder", px(16), theme.TEXT_3), bg=theme.PANEL).pack(
                side="left", padx=(px(8), px(10)))
            path_label = tk.Label(row, font=theme.FONTS["body"], fg=theme.TEXT, bg=theme.PANEL, anchor="w",
                                  width=1)
            path_label.pack(side="left", fill="x", expand=True)
            path_label.bind("<Configure>", lambda e, lbl=path_label, f=folder: lbl.configure(
                text=theme.elide_start(f, theme.FONTS["body"], e.width - px(4))))

    def _add(self) -> None:
        folder = filedialog.askdirectory(parent=self, title=t(self.app.lang, "select_folder_dialog"))
        if folder and self.app.config_store.add_folder(folder):
            self._render()
            self.app.rescan()

    def _remove(self, folder: str) -> None:
        self.app.config_store.remove_folder(folder)
        self._render()
        self.app.rescan()


class App(tk.Tk):
    def __init__(self):
        _enable_dpi_awareness()
        super().__init__(className="HOI4MusicPlayer")
        self.withdraw()
        families = fonts.register_bundled_fonts(self)
        theme.init(self, families)
        setup_styles(self)
        _style_stock_widgets(self)

        self.config_store = Config()
        self.lang = self.config_store.language

        self.title(t(self.lang, "app_title"))
        self.configure(bg=theme.BG)
        self.geometry(f"{px(1200)}x{px(760)}")
        self.minsize(px(960), px(600))
        self._set_window_icon()

        self.player = PlayerEngine()
        self.player.volume = self.config_store.volume
        self.player.set_shuffle(self.config_store.shuffle)
        self.player.set_repeat(RepeatMode(self.config_store.repeat))
        self.player.on_track_change = self._on_track_change
        self.player.on_playback_state_change = self._on_playback_state_change

        self.stations: list[Station] = []
        self._station_key_by_path: dict[Path, str] = {}
        self.empty_mod_names: list[str] = []
        self.selected_station_key: Optional[str] = None
        self.current_display_tracks: list[Track] = []
        self._scanning = False
        self._search_after_id: Optional[str] = None
        self._duration_backlog: list[Track] = []
        self._volume_before_mute = self.config_store.volume or 0.7
        self._page_title_text = ""
        self._now_texts = ("", "")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._schedule_search_refresh())

        self._build()
        self._bind_keys()
        self._apply_language()
        self._on_track_change(None)

        self.deiconify()
        _dark_title_bar(self)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.rescan()
        self._tick()

    def _set_window_icon(self) -> None:
        # Generated in-process, so a packaged build needs no icon files.
        try:
            self._icon_photos = [ImageTk.PhotoImage(app_icon(size)) for size in (16, 24, 32, 48, 64, 128, 256)]
            self.iconphoto(True, *self._icon_photos)
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                self.iconbitmap(default=str(temp_ico_path()))
            except Exception:
                pass

    # ------------------------------------------------------------- layout
    def _build(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self._build_sidebar()
        tk.Frame(self, bg=theme.LINE, width=1).grid(row=0, column=1, sticky="ns")
        self._build_content()
        self._build_deck()

    def _build_sidebar(self) -> None:
        side = tk.Frame(self, bg=theme.SURFACE, width=px(SIDEBAR_WIDTH))
        side.grid(row=0, column=0, sticky="ns")
        side.pack_propagate(False)

        brand = tk.Frame(side, bg=theme.SURFACE, height=px(TOOLBAR_HEIGHT))
        brand.pack(fill="x")
        brand.pack_propagate(False)
        self._logo = ImageTk.PhotoImage(app_icon(px(30)))
        tk.Label(brand, image=self._logo, bg=theme.SURFACE).pack(side="left", padx=(px(18), px(11)))
        self.brand_label = tk.Label(brand, font=theme.FONTS["brand"], fg=theme.TEXT, bg=theme.SURFACE)
        self.brand_label.pack(side="left")
        tk.Frame(side, bg=theme.LINE, height=1).pack(fill="x")

        self.stations_label = tk.Label(side, font=theme.FONTS["label"], fg=theme.TEXT_3, bg=theme.SURFACE,
                                       anchor="w")
        self.stations_label.pack(fill="x", padx=px(18), pady=(px(18), px(6)))
        self.station_list = StationList(side, on_select=self._select_station, on_toggle=self._toggle_station,
                                        on_activate=self._play_station)
        self.station_list.pack(fill="both", expand=True, pady=(0, px(8)))

    def _build_content(self) -> None:
        content = tk.Frame(self, bg=theme.PANEL)
        content.grid(row=0, column=2, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(3, weight=1)

        toolbar = tk.Frame(content, bg=theme.PANEL, height=px(TOOLBAR_HEIGHT))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.pack_propagate(False)
        self.lang_switch = LangSwitch(toolbar, i18n.LANGUAGES, self.lang, self._set_language, bg=theme.PANEL)
        self.lang_switch.pack(side="right", padx=(px(6), px(22)))
        tk.Frame(toolbar, bg=theme.LINE, width=1).pack(side="right", fill="y", pady=px(20), padx=px(8))
        self.folders_btn = FlatButton(toolbar, icon="folder", command=self._open_folders, bg=theme.PANEL)
        self.folders_btn.pack(side="right")
        self.refresh_btn = FlatButton(toolbar, icon="refresh", command=self.rescan, bg=theme.PANEL, padx=9,
                                      tooltip=lambda: t(self.lang, "rescan"))
        self.refresh_btn.pack(side="right", padx=(0, px(2)))
        self.search = SearchBox(toolbar, self.search_var, "")
        self.search.entry.configure(width=34)
        self.search.pack(side="left", padx=(px(24), px(16)), pady=px(14))
        tk.Frame(content, bg=theme.LINE, height=1).grid(row=1, column=0, sticky="ew")

        header = tk.Frame(content, bg=theme.PANEL)
        header.grid(row=2, column=0, sticky="ew", padx=px(26), pady=(px(24), px(16)))
        header.grid_columnconfigure(0, weight=1)
        self.page_title = tk.Label(header, font=theme.FONTS["page_title"], fg=theme.TEXT, bg=theme.PANEL,
                                   anchor="w", width=1)
        self.page_title.grid(row=0, column=0, sticky="ew")
        self.page_title.bind("<Configure>", lambda e: self._render_page_title())
        self.page_meta = tk.Label(header, font=theme.FONTS["mono"], fg=theme.TEXT_2, bg=theme.PANEL, anchor="w")
        self.page_meta.grid(row=1, column=0, sticky="w", pady=(px(3), 0))
        self.play_btn = FlatButton(header, icon="play", variant="primary", command=self._play_all,
                                   bg=theme.PANEL, padx=18, pady=9)
        self.play_btn.grid(row=0, column=1, rowspan=2, sticky="e", padx=(px(16), 0))

        body = tk.Frame(content, bg=theme.PANEL)
        body.grid(row=3, column=0, sticky="nsew", padx=(px(14), 0))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        self.table = TrackTable(body, on_play=self._play_track, headings=self._headings())
        self.table.grid(row=0, column=0, sticky="nsew")
        # Both stay gridded in the same cell; whichever is needed is raised.
        self.empty_state = EmptyState(body)
        self.empty_state.grid(row=0, column=0, sticky="nsew")
        self.empty_state.lower(self.table)

    def _build_deck(self) -> None:
        deck = tk.Frame(self, bg=theme.SURFACE)
        deck.grid(row=1, column=0, columnspan=3, sticky="ew")
        tk.Frame(deck, bg=theme.LINE, height=1).pack(fill="x")

        strip = tk.Frame(deck, bg=theme.SURFACE)
        strip.pack(fill="x", padx=px(22), pady=(px(10), 0))
        self.elapsed_label = tk.Label(strip, text="0:00", font=theme.FONTS["mono"], fg=theme.TEXT_2,
                                      bg=theme.SURFACE, width=5, anchor="w")
        self.elapsed_label.pack(side="left", anchor="s", pady=(0, px(2)))
        self.total_label = tk.Label(strip, font=theme.FONTS["mono"], fg=theme.TEXT_3, bg=theme.SURFACE,
                                    width=5, anchor="e")
        self.total_label.pack(side="right", anchor="s", pady=(0, px(2)))
        self.dial = Dial(strip, bg=theme.SURFACE, on_drag=self._on_dial_drag, on_seek=self._on_dial_seek)
        self.dial.pack(side="left", fill="x", expand=True, padx=px(10))

        row = tk.Frame(deck, bg=theme.SURFACE)
        row.pack(fill="x", padx=px(22), pady=(px(8), px(16)))
        row.grid_columnconfigure(0, weight=1, uniform="side")
        row.grid_columnconfigure(2, weight=1, uniform="side")

        now = tk.Frame(row, bg=theme.SURFACE)
        now.grid(row=0, column=0, sticky="ew")
        self.cover_label = tk.Label(now, bg=theme.SURFACE, cursor="hand2")
        self.cover_label.pack(side="left")
        text_col = tk.Frame(now, bg=theme.SURFACE)
        text_col.pack(side="left", fill="x", expand=True, padx=(px(14), px(12)))
        self.now_title = tk.Label(text_col, font=theme.FONTS["now_title"], fg=theme.TEXT, bg=theme.SURFACE,
                                  anchor="w", width=1, cursor="hand2")
        self.now_title.pack(fill="x")
        self.now_sub = tk.Label(text_col, font=theme.FONTS["small"], fg=theme.TEXT_2, bg=theme.SURFACE,
                                anchor="w", width=1)
        self.now_sub.pack(fill="x", pady=(px(1), 0))
        self.now_title.bind("<Configure>", lambda e: self._render_now_texts())
        for widget in (self.cover_label, self.now_title):
            widget.bind("<Button-1>", lambda e: self.table.reveal_playing())

        transport = tk.Frame(row, bg=theme.SURFACE)
        transport.grid(row=0, column=1)
        button = dict(bg=theme.SURFACE, icon_size=18, padx=9, pady=9)
        self.shuffle_btn = FlatButton(transport, icon="shuffle", variant="toggle", command=self._toggle_shuffle,
                                      tooltip=lambda: t(self.lang, "shuffle"), **button)
        self.shuffle_btn.pack(side="left", padx=(0, px(10)))
        FlatButton(transport, icon="prev", command=self.player.previous, **button).pack(side="left")
        self.play_knob = KnobButton(transport, 46, command=self._toggle_play_pause, bg=theme.SURFACE)
        self.play_knob.pack(side="left", padx=px(12))
        FlatButton(transport, icon="next", command=self.player.next, **button).pack(side="left")
        self.repeat_btn = FlatButton(transport, icon="repeat", variant="toggle", command=self._cycle_repeat,
                                     tooltip=lambda: t(self.lang, "repeat"), **button)
        self.repeat_btn.pack(side="left", padx=(px(10), 0))
        self._sync_mode_buttons()

        volume = tk.Frame(row, bg=theme.SURFACE)
        volume.grid(row=0, column=2, sticky="e")
        self.volume_btn = FlatButton(volume, icon=self._volume_icon(self.config_store.volume),
                                     command=self._toggle_mute, **button)
        self.volume_btn.pack(side="left", padx=(0, px(6)))
        self.volume_slider = Slider(volume, 124, bg=theme.SURFACE, value=self.config_store.volume,
                                    on_change=self._on_volume_change)
        self.volume_slider.pack(side="left")

    def _bind_keys(self) -> None:
        self.bind_all("<space>", self._on_space)
        self.bind_all("<Control-f>", lambda e: (self.search.entry.focus_set(), "break")[1])
        self.bind_all("<Escape>", self._on_escape)

    # --------------------------------------------------------------- i18n
    def _headings(self) -> dict[str, str]:
        return {key: t(self.lang, f"col_{key}") for key in ("title", "author", "station", "mod", "time")}

    def _set_language(self, lang: str) -> None:
        if lang == self.lang:
            return
        self.lang = lang
        self.config_store.language = lang
        self._apply_language()
        self.rescan()  # track/station titles come from the mods' own localisation

    def _apply_language(self) -> None:
        lang = self.lang
        self.title(t(lang, "app_title"))
        self.brand_label.configure(text=t(lang, "app_title"))
        self.stations_label.configure(text=t(lang, "stations").upper())
        self.search.set_placeholder(t(lang, "search_placeholder"))
        self.folders_btn.set_text(t(lang, "folders"))
        self.play_btn.set_text(t(lang, "play"))
        self.lang_switch.set(lang)
        self.table.set_headings(self._headings())
        self.table.unknown_author = t(lang, "unknown_author")
        if self.player.current_track is None:
            self._on_track_change(None)
        self._render_station_list()
        self._refresh_track_list()

    # ----------------------------------------------------------- scanning
    def rescan(self) -> None:
        if self._scanning:
            return
        folders = self.config_store.folders
        if not folders:
            self._on_scan_complete([], [])
            return
        self._scanning = True
        self._refresh_track_list()
        language = self.lang

        def work():
            stations, empty_mod_names = scan_folders_detailed([Path(f) for f in folders], language)
            self.after(0, lambda: self._on_scan_complete(stations, empty_mod_names))

        threading.Thread(target=work, daemon=True).start()

    def _on_scan_complete(self, stations: list[Station], empty_mod_names: list[str]) -> None:
        self._scanning = False
        self.stations = stations
        self._station_key_by_path = {track.file_path: s.key for s in stations for track in s.tracks}
        self.empty_mod_names = list(empty_mod_names)
        if self.selected_station_key not in {s.key for s in stations}:
            self.selected_station_key = None
        self._render_station_list()
        self._refresh_track_list()

        # Durations are read on the main thread in small batches: reading them
        # on a worker thread alongside pygame's mixer and the Tk mainloop
        # crashed the interpreter (GIL corruption).
        self._duration_backlog = [track for s in stations for track in s.tracks if track.duration is None]
        if self._duration_backlog:
            self.after(50, self._process_duration_backlog)

    def _process_duration_backlog(self) -> None:
        batch, self._duration_backlog = self._duration_backlog[:5], self._duration_backlog[5:]
        for track in batch:
            compute_track_duration(track)
            self.table.update_track_duration(track)
        if self._duration_backlog:
            self.after(15, self._process_duration_backlog)

    def _open_folders(self) -> None:
        FoldersDialog(self)

    def _add_folder_directly(self) -> None:
        folder = filedialog.askdirectory(parent=self, title=t(self.lang, "select_folder_dialog"))
        if folder and self.config_store.add_folder(folder):
            self.rescan()

    # ------------------------------------------------------------ stations
    def _enabled_stations(self) -> list[Station]:
        disabled = self.config_store.disabled_station_keys
        return [s for s in self.stations if s.key not in disabled]

    def _render_station_list(self) -> None:
        lang = self.lang
        disabled = self.config_store.disabled_station_keys
        rows: list[StationRowData] = []
        if self.stations:
            total = sum(s.track_count for s in self._enabled_stations())
            rows.append(StationRowData(
                None, t(lang, "all_stations"), i18n.count(lang, len(self.stations), "station"),
                i18n.number(lang, total),
            ))
        for station in self.stations:
            sub = station.mod_name if station.mod_name != station.name else ""
            rows.append(StationRowData(
                station.key, station.name, sub, i18n.number(lang, station.track_count),
                enabled=station.key not in disabled,
            ))
        self.station_list.set_rows(rows, self.selected_station_key)

    def _toggle_station(self, key: str, enabled: bool) -> None:
        self.config_store.set_station_enabled(key, enabled)
        self._render_station_list()
        self._refresh_track_list()

    def _select_station(self, key: Optional[str]) -> None:
        self.selected_station_key = key
        self.station_list.set_selected(key)
        self._refresh_track_list()

    def _play_station(self, key: Optional[str]) -> None:
        self._select_station(key)
        self._play_all()

    # -------------------------------------------------------------- tracks
    def _schedule_search_refresh(self) -> None:
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(180, self._run_scheduled_search_refresh)

    def _run_scheduled_search_refresh(self) -> None:
        self._search_after_id = None
        self._refresh_track_list()

    def _visible_stations(self) -> list[Station]:
        # A disabled station's tracks never show up or play anywhere - the
        # lamp is the single source of truth for that.
        enabled = self._enabled_stations()
        if self.selected_station_key is not None:
            return [s for s in enabled if s.key == self.selected_station_key]
        return enabled

    def _selected_station(self) -> Optional[Station]:
        return next((s for s in self.stations if s.key == self.selected_station_key), None)

    def _refresh_track_list(self) -> None:
        query = self.search_var.get().strip().lower()
        tracks: list[Track] = [track for station in self._visible_stations() for track in station.tracks]
        if query:
            tracks = [
                tr for tr in tracks
                if query in tr.display_name.lower()
                or query in tr.mod_name.lower()
                or query in tr.mod_author.lower()
                or query in tr.station_name.lower()
            ]
        tracks.sort(key=lambda tr: (tr.station_name.lower(), tr.track_title.lower()))
        self.current_display_tracks = tracks
        self._render_page_header(len(tracks))
        self._render_now_texts()

        if tracks:
            self.empty_state.lower(self.table)
            self.play_btn.grid()
            current = self.player.current_track
            self.table.set_tracks(tracks, current.file_path if current is not None else None,
                                  single_station=self.selected_station_key is not None)
        else:
            self.table.set_tracks([], None)
            self.play_btn.grid_remove()
            self._show_empty_state(query)
            self.empty_state.tkraise()

    def _show_empty_state(self, query: str) -> None:
        lang = self.lang
        station = self._selected_station()
        if not self.config_store.folders:
            self.empty_state.show(t(lang, "empty_start_title"), t(lang, "empty_start_body"),
                                  (t(lang, "add_folder"), "primary", self._add_folder_directly))
        elif self._scanning and not self.stations:
            self.empty_state.show(t(lang, "scanning"))
        elif not self.stations:
            if self.empty_mod_names:
                names = ", ".join(self.empty_mod_names[:3])
                if len(self.empty_mod_names) > 3:
                    names += f" (+{len(self.empty_mod_names) - 3})"
                body = t(lang, "found_empty_mods", names=names)
            else:
                body = t(lang, "no_mod_found")
            self.empty_state.show(t(lang, "empty_none_title"), body,
                                  (t(lang, "manage_folders"), "secondary", self._open_folders))
        elif station is not None and station.key in self.config_store.disabled_station_keys:
            self.empty_state.show(t(lang, "empty_off_title"), t(lang, "empty_off_body"),
                                  (t(lang, "turn_on"), "secondary", lambda: self._toggle_station(station.key, True)))
        elif query:
            self.empty_state.show(t(lang, "empty_search_title"),
                                  t(lang, "empty_search_body", query=self.search_var.get().strip()),
                                  (t(lang, "clear_search"), "secondary", lambda: self.search_var.set("")))
        else:
            self.empty_state.show(t(lang, "empty_none_title"))

    def _render_page_header(self, visible_count: int) -> None:
        lang = self.lang
        station = self._selected_station()
        if station is None:
            self._page_title_text = t(lang, "all_stations")
            meta = []
            if self.stations:
                meta = [i18n.count(lang, len(self.stations), "station"), i18n.count(lang, visible_count, "track")]
                if self.empty_mod_names:
                    meta.append(i18n.count(lang, len(self.empty_mod_names), "mod_without_music"))
        else:
            self._page_title_text = station.name
            meta = [station.mod_name] if station.mod_name != station.name else []
            searching = bool(self.search_var.get().strip())
            meta.append(i18n.count(lang, visible_count if searching else station.track_count, "track"))
        if self._scanning:
            meta = [t(lang, "scanning")]
        self.page_meta.configure(text="  ·  ".join(meta).upper())
        self._render_page_title()

    def _render_page_title(self) -> None:
        width = self.page_title.winfo_width()
        text = self._page_title_text
        if width > 1:
            text = theme.elide(text, theme.FONTS["page_title"], width - px(4))
        self.page_title.configure(text=text)

    def _play_all(self) -> None:
        if self.current_display_tracks:
            self._play_track(self.current_display_tracks[0])

    def _play_track(self, track: Track) -> None:
        self.player.set_queue(self.current_display_tracks, start_track=track)
        self.player.play()

    # ----------------------------------------------------------- transport
    def _toggle_play_pause(self) -> None:
        if self.player.current_track is None:
            self._play_all()
            return
        self.player.toggle_pause()

    def _toggle_shuffle(self) -> None:
        enabled = not self.player.shuffle
        self.player.set_shuffle(enabled)
        self.config_store.shuffle = enabled
        self._sync_mode_buttons()

    def _cycle_repeat(self) -> None:
        order = [RepeatMode.OFF, RepeatMode.ALL, RepeatMode.ONE]
        mode = order[(order.index(self.player.repeat) + 1) % len(order)]
        self.player.set_repeat(mode)
        self.config_store.repeat = mode.value
        self._sync_mode_buttons()

    def _sync_mode_buttons(self) -> None:
        self.shuffle_btn.set_active(self.player.shuffle)
        repeat = self.player.repeat
        self.repeat_btn.set_icon("repeat_one" if repeat == RepeatMode.ONE else "repeat")
        self.repeat_btn.set_active(repeat != RepeatMode.OFF)

    @staticmethod
    def _volume_icon(volume: float) -> str:
        if volume <= 0.001:
            return "volume_mute"
        return "volume_low" if volume < 0.5 else "volume_high"

    def _on_volume_change(self, volume: float) -> None:
        self.player.set_volume(volume)
        self.config_store.volume = volume
        if volume > 0.001:
            self._volume_before_mute = volume
        self.volume_btn.set_icon(self._volume_icon(volume))

    def _toggle_mute(self) -> None:
        target = self._volume_before_mute if self.player.volume <= 0.001 else 0.0
        self.volume_slider.set(target, notify=True)

    def _on_dial_drag(self, fraction: float) -> None:
        duration = self.player.get_duration_seconds()
        if duration:
            self.elapsed_label.configure(text=format_time(fraction * duration))

    def _on_dial_seek(self, fraction: float) -> None:
        duration = self.player.get_duration_seconds()
        if duration:
            self.player.seek(fraction * duration)

    # ------------------------------------------------------------ callbacks
    def _on_track_change(self, track: Optional[Track]) -> None:
        if track is None:
            self._now_texts = (t(self.lang, "nothing_playing"), "")
            self.now_title.configure(fg=theme.TEXT_2)
            self.cover_label.configure(image=cover_photo(None, px(COVER_SIZE), radius=px(4)))
            self.elapsed_label.configure(text="0:00")
            self.total_label.configure(text=format_time(None))
            self.dial.set_state(0.0, None, active=False)
            self.play_knob.set_glyph("play")
        else:
            author = track.track_author or t(self.lang, "unknown_author")
            self._now_texts = (track.track_title, f"{author}  ·  {track.mod_name}")
            self.now_title.configure(fg=theme.TEXT)
            self.cover_label.configure(image=cover_photo(track.icon, px(COVER_SIZE), radius=px(4)))
            if track.duration is None:
                # Short delay so this never competes with playback starting.
                self.after(30, lambda tr=track: self._maybe_fetch_duration(tr))
        self._render_now_texts()
        self.table.set_playing(track.file_path if track is not None else None)
        self.station_list.set_live(self._station_key_by_path.get(track.file_path) if track is not None else None)

    def _render_now_texts(self) -> None:
        title, sub = self._now_texts
        if self.player.current_track is None and self.current_display_tracks:
            sub = t(self.lang, "pick_track_hint")
        width = self.now_title.winfo_width()
        if width > 1:
            title = theme.elide(title, theme.FONTS["now_title"], width - px(4))
            sub = theme.elide(sub, theme.FONTS["small"], width - px(4))
        self.now_title.configure(text=title)
        self.now_sub.configure(text=sub)

    def _maybe_fetch_duration(self, track: Track) -> None:
        if self.player.current_track is track:
            compute_track_duration(track)
            self.table.update_track_duration(track)

    def _on_playback_state_change(self, playing: bool) -> None:
        self.play_knob.set_glyph("pause" if playing else "play")

    # ------------------------------------------------------------- keyboard
    def _typing(self) -> bool:
        return isinstance(self.focus_get(), tk.Entry)

    def _on_space(self, _e):
        if self._typing():
            return None
        self._toggle_play_pause()
        return "break"

    def _on_escape(self, _e):
        if self.search_var.get():
            self.search_var.set("")
        self.table.tree.focus_set()

    # ----------------------------------------------------------------- loop
    def _tick(self) -> None:
        self.player.poll_events()
        track = self.player.current_track
        if track is not None:
            duration = self.player.get_duration_seconds()
            position = self.player.get_position_seconds()
            if not self.dial.dragging:
                self.elapsed_label.configure(text=format_time(position))
            self.total_label.configure(text=format_time(duration))
            fraction = min(1.0, position / duration) if duration else 0.0
            self.dial.set_state(fraction, duration, active=True)
            self.play_knob.set_glyph("pause" if self.player.is_playing else "play")
        self.after(250, self._tick)

    def _on_close(self) -> None:
        self.player.stop()
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
