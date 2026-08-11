"""CustomTkinter-based UI for the HOI4 Music Player."""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from tkinter import ttk
from typing import Optional

import customtkinter as ctk
from tkinter import filedialog
from PIL import ImageTk

from . import i18n, theme
from .config import Config
from .duration import compute_track_duration
from .i18n import t
from .icons import (
    folder_icon,
    next_icon,
    pause_icon,
    play_icon,
    previous_icon,
    refresh_icon,
    volume_icon,
)
from .mod_scanner import scan_folders_detailed
from .models import Station, Track
from .player_engine import PlayerEngine
from .utils import (
    format_time,
    get_app_icon_image,
    get_app_icon_ico_path,
    get_icon_image,
    get_icon_photo,
)

ctk.set_appearance_mode("dark")

SIDEBAR_ICON_SIZE = 40
NOWPLAYING_ICON_SIZE = 56
SIDEBAR_WIDTH = 320

_ROW_COLORS = {
    "normal": theme.BG_ROW,
    "hover": theme.BG_ROW_HOVER,
    "selected": theme.BG_ROW_SELECTED,
    "playing": theme.BG_ROW_PLAYING,
}


# Static wrap width for sidebar station rows, rather than clipping long
# names. A dynamic (per-resize) wraplength and a resizable sidebar were
# both tried and reverted - see gui.py history/README - reconfiguring
# widget geometry on every pixel of drag/resize motion made customtkinter's
# canvas redraw fall behind and leave visible artifacts on screen.
SIDEBAR_LABEL_WRAP = 230


class _HoverRow(ctk.CTkFrame):
    """A CTkFrame that lightens on hover and supports a persistent
    selected/playing highlight state."""

    def __init__(self, master, **kwargs):
        # corner_radius=0 / border_width=0: rounded corners and borders are
        # redrawn on canvas on every resize, which gets expensive with
        # hundreds of rows in a mod's track list. Flat rows + spacing
        # between them (see .pack(pady=...) at the call sites) look almost
        # identical and are far cheaper to keep redrawing while resizing.
        kwargs.setdefault("corner_radius", 0)
        kwargs.setdefault("fg_color", theme.BG_ROW)
        kwargs.setdefault("border_width", 0)
        super().__init__(master, **kwargs)
        self._state = "normal"

    def _bind_hover(self, widget):
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, _event=None):
        if self._state == "normal":
            self.configure(fg_color=_ROW_COLORS["hover"])

    def _on_leave(self, _event=None):
        self.configure(fg_color=_ROW_COLORS[self._state])

    def set_state(self, state: str):
        self._state = state
        self.configure(fg_color=_ROW_COLORS[state])


class StationRow(_HoverRow):
    def __init__(self, master, station: Station, enabled: bool, on_toggle, on_select, lang: str = "en"):
        super().__init__(master)
        self.station = station
        self.on_select = on_select

        self.grid_columnconfigure(2, weight=1)

        self.checkbox_var = ctk.BooleanVar(value=enabled)
        checkbox = ctk.CTkCheckBox(
            self, text="", variable=self.checkbox_var, width=20,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            checkmark_color=theme.ACCENT_TEXT, border_color=theme.TEXT_MUTED,
            command=lambda: on_toggle(station.key, self.checkbox_var.get()),
        )
        checkbox.grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=8)

        icon_label = ctk.CTkLabel(self, text="", image=get_icon_image(station.mod_icon, SIDEBAR_ICON_SIZE))
        icon_label.grid(row=0, column=1, rowspan=2, padx=(2, 10), pady=8)

        name_label = ctk.CTkLabel(
            self, text=station.name, anchor="w", text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(weight="bold"), wraplength=SIDEBAR_LABEL_WRAP, justify="left",
        )
        name_label.grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=(8, 0))

        subtitle = t(lang, "station_subtitle", mod=station.mod_name, count=station.track_count)
        sub_label = ctk.CTkLabel(
            self, text=subtitle, anchor="w", font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY, wraplength=SIDEBAR_LABEL_WRAP, justify="left",
        )
        sub_label.grid(row=1, column=2, sticky="ew", padx=(0, 10), pady=(0, 8))

        for widget in (self, icon_label, name_label, sub_label):
            widget.bind("<Button-1>", lambda e: self.on_select(station.key))
            self._bind_hover(widget)

    def set_selected(self, selected: bool):
        self.set_state("selected" if selected else "normal")


class TrackListView(ttk.Frame):
    """The track list, backed by a native ttk.Treeview instead of one
    CTkFrame-based row per track.

    A CTkFrame/CTkLabel/CTkButton row per track was the original design,
    but creating a few thousand of them synchronously (a real HOI4 library
    can run 2000-3000+ tracks) reliably froze the whole app - Windows
    reported it as "Not Responding" and it never recovered, which is
    exactly what looks like a crash to a user. ttk.Treeview is a real
    virtualized widget (implemented natively in Tk, not built out of our
    own child widgets): it only ever draws the rows currently in the
    visible viewport no matter how many items it holds, so it stays fast
    and responsive at any list size without needing any manual lazy
    creation, pagination, or eviction scheme."""

    ROW_HEIGHT = 34
    ICON_SIZE = 22

    def __init__(self, master, on_play, lang: str = "en"):
        super().__init__(master)
        self.on_play = on_play
        self.lang = lang
        self.tracks: list[Track] = []
        self._path_to_iid: dict[Path, str] = {}

        self._configure_style()

        columns = ("station", "mod", "author", "duration")
        self.tree = ttk.Treeview(
            self, columns=columns, show="tree headings",
            style="Tracks.Treeview", selectmode="browse",
        )
        self._apply_headings()
        self.tree.column("#0", width=320, minwidth=160, anchor="w", stretch=True)
        self.tree.column("station", width=150, minwidth=80, anchor="w", stretch=False)
        self.tree.column("mod", width=170, minwidth=80, anchor="w", stretch=False)
        self.tree.column("author", width=130, minwidth=60, anchor="w", stretch=False)
        self.tree.column("duration", width=60, minwidth=50, anchor="e", stretch=False)
        self.tree.tag_configure("playing", background=theme.BG_ROW_PLAYING)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview, style="Tracks.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-Button-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_enter_key)

    def _apply_headings(self):
        self.tree.heading("#0", text=t(self.lang, "col_track"), anchor="w")
        self.tree.heading("station", text=t(self.lang, "col_station"), anchor="w")
        self.tree.heading("mod", text=t(self.lang, "col_mod"), anchor="w")
        self.tree.heading("author", text=t(self.lang, "col_author"), anchor="w")
        self.tree.heading("duration", text=t(self.lang, "col_time"), anchor="e")

    def set_language(self, lang: str):
        self.lang = lang
        self._apply_headings()

    def _configure_style(self):
        # theme_use("clam") is also set globally in App.__init__ - repeated
        # here too since it must be active before these style.configure()
        # calls for them to stick (Windows' default "vista" ttk theme draws
        # Treeview/Scrollbar natively via the OS and ignores color options
        # like background/troughcolor entirely; "clam" is a full Tk-drawn
        # theme that honors them).
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Tracks.Treeview",
            background=theme.BG_ROW, fieldbackground=theme.BG_ROW,
            foreground=theme.TEXT_PRIMARY, borderwidth=0,
            rowheight=self.ROW_HEIGHT, font=("Segoe UI", 10),
        )
        style.map(
            "Tracks.Treeview",
            background=[("selected", theme.BG_ROW_SELECTED)],
            foreground=[("selected", theme.TEXT_PRIMARY)],
        )
        style.configure(
            "Tracks.Treeview.Heading",
            background=theme.BG_TOPBAR, foreground=theme.TEXT_SECONDARY,
            borderwidth=0, relief="flat", font=("Segoe UI", 9, "bold"),
        )
        style.map("Tracks.Treeview.Heading", background=[("active", theme.BG_TOPBAR)])
        style.configure(
            "Tracks.Vertical.TScrollbar",
            background=theme.BUTTON_NEUTRAL, troughcolor=theme.BG_PANEL,
            bordercolor=theme.BG_PANEL, arrowcolor=theme.TEXT_SECONDARY,
        )

    def set_tracks(self, tracks: list[Track], playing_path: Optional[Path]):
        self.tree.delete(*self.tree.get_children())
        self.tracks = tracks
        self._path_to_iid = {}
        for i, track in enumerate(tracks):
            iid = str(i)
            icon = get_icon_photo(track.mod_icon, self.ICON_SIZE)
            playing = playing_path is not None and track.file_path == playing_path
            author = t(self.lang, "unknown_author") if track.mod_author == "Unknown" else track.mod_author
            self.tree.insert(
                "", "end", iid=iid, text=f" {track.display_name}", image=icon,
                values=(track.station_name, track.mod_name, author, format_time(track.duration)),
                tags=("playing",) if playing else (),
            )
            self._path_to_iid[track.file_path] = iid
        if playing_path is not None and playing_path in self._path_to_iid:
            self.tree.see(self._path_to_iid[playing_path])

    def set_playing(self, playing_path: Optional[Path]):
        for iid in self.tree.tag_has("playing"):
            self.tree.item(iid, tags=())
        if playing_path is None:
            return
        iid = self._path_to_iid.get(playing_path)
        if iid is not None:
            self.tree.item(iid, tags=("playing",))
            self.tree.see(iid)

    def update_track_duration(self, track: Track):
        iid = self._path_to_iid.get(track.file_path)
        if iid is not None:
            self.tree.set(iid, "duration", format_time(track.duration))

    def _on_double_click(self, event):
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


def _styled_button(master, **kwargs):
    defaults = dict(
        fg_color=theme.BUTTON_NEUTRAL, hover_color=theme.BUTTON_NEUTRAL_HOVER,
        text_color=theme.TEXT_PRIMARY, corner_radius=8,
    )
    defaults.update(kwargs)
    return ctk.CTkButton(master, **defaults)


class FolderManagerDialog(ctk.CTkToplevel):
    def __init__(self, master, config_store: Config, on_change, lang: str = "en"):
        super().__init__(master)
        self.lang = lang
        self.title(t(lang, "manage_folders_title"))
        self.geometry("580x380")
        self.configure(fg_color=theme.BG_APP)
        self.config_store = config_store
        self.on_change = on_change
        self.transient(master)

        ctk.CTkLabel(
            self, text=t(lang, "manage_folders_body"),
            justify="left", text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=18, pady=(18, 10))

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=theme.BG_PANEL, label_text="")
        self.list_frame.pack(fill="both", expand=True, padx=18, pady=8)

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=18, pady=(0, 18))
        _styled_button(
            button_row, text=t(lang, "add_folder_btn"), image=folder_icon(16, theme.TEXT_PRIMARY),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, text_color=theme.ACCENT_TEXT,
            command=self._add_folder,
        ).pack(side="left")
        _styled_button(button_row, text=t(lang, "close"), command=self.destroy).pack(side="right")

        self._refresh_list()

    def _refresh_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        folders = self.config_store.folders
        if not folders:
            ctk.CTkLabel(
                self.list_frame, text=t(self.lang, "no_folders_yet"), text_color=theme.TEXT_SECONDARY
            ).pack(pady=8)
        for folder in folders:
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=folder, anchor="w", text_color=theme.TEXT_PRIMARY).pack(
                side="left", fill="x", expand=True
            )
            _styled_button(
                row, text=t(self.lang, "remove"), width=76, fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
                command=lambda f=folder: self._remove_folder(f),
            ).pack(side="right")

    def _add_folder(self):
        folder = filedialog.askdirectory(title=t(self.lang, "select_folder_dialog"))
        if folder:
            self.config_store.add_folder(folder)
            self._refresh_list()
            self.on_change()

    def _remove_folder(self, folder: str):
        self.config_store.remove_folder(folder)
        self._refresh_list()
        self.on_change()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config_store = Config()
        self.lang = self.config_store.language

        self.title(t(self.lang, "app_title"))
        self.geometry("1080x700")
        self.minsize(880, 580)
        self.configure(fg_color=theme.BG_APP)
        self._set_window_icon()
        # Set before any ttk (Treeview/Scrollbar) widget is created - see
        # the comment in TrackListView._configure_style for why this
        # specific theme matters.
        ttk.Style(self).theme_use("clam")

        self.player = PlayerEngine()
        self.player.volume = self.config_store.volume
        self.player.on_track_change = self._on_track_change
        self.player.on_playback_state_change = self._on_playback_state_change

        self.stations: list[Station] = []
        self.station_rows: dict[str, StationRow] = {}
        self.selected_station_key: Optional[str] = None
        self.current_display_tracks: list[Track] = []
        self._scanning = False
        self._search_after_id: Optional[str] = None
        self._duration_backlog: list[Track] = []

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._schedule_search_refresh())

        self._build_layout()
        self.rescan()
        self._tick()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_window_icon(self):
        # PyInstaller's --icon only sets the .exe file's icon in Explorer,
        # not the running window/taskbar icon (which was showing Tk's
        # default feather logo) - it has to be set at runtime too. Generate
        # the icon in-process (see utils.get_app_icon_image) rather than
        # loading a bundled file, so the packaged .exe doesn't need any
        # asset files shipped alongside it.
        try:
            # Passing several sizes lets Tk/the window manager pick the best
            # fit for each context (title bar, taskbar, Alt-Tab) instead of
            # scaling a single 64px image, which looked soft when shrunk
            # down for a small taskbar slot.
            self._window_icon_photos = [
                ImageTk.PhotoImage(get_app_icon_image(size)) for size in (16, 24, 32, 48, 64, 128)
            ]
            self.iconphoto(True, *self._window_icon_photos)
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                self.iconbitmap(str(get_app_icon_ico_path()))
            except Exception:
                pass

    # --------------------------------------------------------------- i18n
    def _other_language(self) -> str:
        others = [code for code in i18n.LANGUAGES if code != self.lang]
        return others[0] if others else self.lang

    def _toggle_language(self):
        self.lang = self._other_language()
        self.config_store.language = self.lang
        self._apply_language()
        self.rescan()  # re-resolve track/station titles in the new language

    def _apply_language(self):
        self.title(t(self.lang, "app_title"))
        self.brand_label.configure(text=t(self.lang, "app_title"))
        self.manage_folders_btn.configure(text=t(self.lang, "manage_folders"))
        self.search_entry.configure(placeholder_text=t(self.lang, "search_placeholder"))
        self.language_btn.configure(text=self._other_language().upper())
        self.stations_header_label.configure(text=t(self.lang, "stations"))
        self.all_stations_row.configure(text=t(self.lang, "all_stations"))
        self.play_all_btn.configure(text=t(self.lang, "play_all"))
        self.track_list_view.set_language(self.lang)
        self.empty_tracks_label.configure(text=t(self.lang, "no_tracks_message"))
        if self.player.current_track is None:
            self.now_title_label.configure(text=t(self.lang, "nothing_playing"))
            self.now_meta_label.configure(text=t(self.lang, "add_folder_hint"))

    # ------------------------------------------------------------------ UI
    def _build_layout(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top bar
        top_bar = ctk.CTkFrame(self, corner_radius=0, fg_color=theme.BG_TOPBAR, height=58)
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        top_bar.grid_propagate(False)

        brand = ctk.CTkFrame(top_bar, fg_color="transparent")
        brand.pack(side="left", padx=(16, 24))
        ctk.CTkLabel(brand, text="", image=get_icon_image(None, 28)).pack(side="left", padx=(0, 8))
        self.brand_label = ctk.CTkLabel(
            brand, text=t(self.lang, "app_title"), font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.brand_label.pack(side="left")

        self.manage_folders_btn = _styled_button(
            top_bar, text=t(self.lang, "manage_folders"), image=folder_icon(16, theme.TEXT_PRIMARY),
            command=self._open_folder_manager,
        )
        self.manage_folders_btn.pack(side="left", padx=(0, 8), pady=10)
        _styled_button(
            top_bar, text="", image=refresh_icon(16, theme.TEXT_PRIMARY), width=36,
            command=self.rescan,
        ).pack(side="left", pady=10)

        self.status_label = ctk.CTkLabel(top_bar, text="", text_color=theme.TEXT_SECONDARY)
        self.status_label.pack(side="left", padx=14)

        self.search_entry = ctk.CTkEntry(
            top_bar, placeholder_text=t(self.lang, "search_placeholder"),
            textvariable=self.search_var, width=260, fg_color=theme.BG_ROW,
            border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY,
        )
        self.search_entry.pack(side="right", padx=16, pady=10)

        self.language_btn = _styled_button(
            top_bar, text=self._other_language().upper(), width=44,
            command=self._toggle_language,
        )
        self.language_btn.pack(side="right", padx=(0, 4), pady=10)

        # Sidebar (stations). Fixed width - a live drag-to-resize handle was
        # tried and reverted: CTkFrame's canvas redraw couldn't keep up
        # with rapid <B1-Motion> events and left visible ghost artifacts on
        # screen. Long station names just wrap onto extra lines instead
        # (see SIDEBAR_LABEL_WRAP), so a fixed width doesn't clip anything.
        self.sidebar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=theme.BG_SIDEBAR)
        self.sidebar.grid(row=1, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)
        self.stations_header_label = ctk.CTkLabel(
            self.sidebar, text=t(self.lang, "stations"), font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_MUTED,
        )
        self.stations_header_label.pack(anchor="w", padx=16, pady=(16, 6))
        self.all_stations_row = _styled_button(
            self.sidebar, text=t(self.lang, "all_stations"), anchor="w",
            fg_color=theme.BG_ROW_SELECTED, hover_color=theme.BG_ROW_HOVER,
            command=lambda: self._select_station(None),
        )
        self.all_stations_row.pack(fill="x", padx=14, pady=(0, 10))

        self.stations_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", label_text="")
        self.stations_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Track list
        track_panel = ctk.CTkFrame(self, corner_radius=0, fg_color=theme.BG_PANEL)
        track_panel.grid(row=1, column=1, sticky="nsew")
        track_panel.grid_rowconfigure(1, weight=1)
        track_panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(track_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.track_count_label = ctk.CTkLabel(
            header, text=t(self.lang, "tracks_header", count=0), font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.track_count_label.pack(side="left")
        self.play_all_btn = _styled_button(
            header, text=t(self.lang, "play_all"), image=play_icon(14, theme.ACCENT_TEXT), width=110,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, text_color=theme.ACCENT_TEXT,
            command=self._play_all,
        )
        self.play_all_btn.pack(side="right")

        self.track_list_view = TrackListView(track_panel, on_play=self._play_track, lang=self.lang)
        self.track_list_view.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))

        self.empty_tracks_label = ctk.CTkLabel(
            track_panel, text=t(self.lang, "no_tracks_message"),
            wraplength=520, justify="left", text_color=theme.TEXT_SECONDARY,
        )
        self.empty_tracks_label.grid(row=1, column=0, sticky="nw", padx=14, pady=(4, 14))
        self.empty_tracks_label.grid_remove()

        # Now playing bar
        self._build_now_playing_bar()

    def _build_now_playing_bar(self):
        bar = ctk.CTkFrame(self, height=100, corner_radius=0, fg_color=theme.BG_NOWPLAYING,
                            border_width=0)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        divider = ctk.CTkFrame(self, height=1, fg_color=theme.BORDER, corner_radius=0)
        divider.grid(row=2, column=0, columnspan=2, sticky="new")

        self.now_icon_label = ctk.CTkLabel(bar, text="", image=get_icon_image(None, NOWPLAYING_ICON_SIZE))
        self.now_icon_label.grid(row=0, column=0, rowspan=3, padx=14, pady=12)

        self.now_title_label = ctk.CTkLabel(
            bar, text=t(self.lang, "nothing_playing"), anchor="w", font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.now_title_label.grid(row=0, column=1, sticky="ew", padx=8, pady=(12, 0))

        self.now_meta_label = ctk.CTkLabel(
            bar, text=t(self.lang, "add_folder_hint"), anchor="w",
            text_color=theme.TEXT_SECONDARY,
        )
        self.now_meta_label.grid(row=1, column=1, sticky="ew", padx=8)

        progress_row = ctk.CTkFrame(bar, fg_color="transparent")
        progress_row.grid(row=2, column=1, sticky="ew", padx=8, pady=(4, 10))
        progress_row.grid_columnconfigure(1, weight=1)
        self.elapsed_label = ctk.CTkLabel(progress_row, text="0:00", width=40, text_color=theme.TEXT_SECONDARY)
        self.elapsed_label.grid(row=0, column=0)
        # A CTkSlider, not a CTkProgressBar - lets the user click/drag to
        # seek. _seeking tracks whether the user currently has the handle
        # grabbed, so the periodic playback-position update in _tick()
        # doesn't fight the drag.
        self._seeking = False
        self.progress_bar = ctk.CTkSlider(
            progress_row, from_=0, to=1, number_of_steps=1000,
            progress_color=theme.ACCENT, button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER, fg_color=theme.BUTTON_NEUTRAL,
            command=self._on_seek_drag,
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=10)
        self.progress_bar.bind("<ButtonPress-1>", self._on_seek_start, add="+")
        self.progress_bar.bind("<ButtonRelease-1>", self._on_seek_end, add="+")
        self.duration_label = ctk.CTkLabel(progress_row, text="--:--", width=40, text_color=theme.TEXT_SECONDARY)
        self.duration_label.grid(row=0, column=2)

        controls = ctk.CTkFrame(bar, fg_color="transparent")
        controls.grid(row=0, column=2, rowspan=3, padx=16)

        transport = ctk.CTkFrame(controls, fg_color="transparent")
        transport.pack()

        _styled_button(
            transport, text="", image=previous_icon(16, theme.TEXT_PRIMARY), width=34, height=34,
            corner_radius=17, command=self.player.previous,
        ).pack(side="left", padx=3)

        self.play_pause_btn = _styled_button(
            transport, text="", image=play_icon(18, theme.ACCENT_TEXT), width=44, height=44,
            corner_radius=22, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=self._toggle_play_pause,
        )
        self.play_pause_btn.pack(side="left", padx=5)

        _styled_button(
            transport, text="", image=next_icon(16, theme.TEXT_PRIMARY), width=34, height=34,
            corner_radius=17, command=lambda: self.player.next(),
        ).pack(side="left", padx=3)

        volume_row = ctk.CTkFrame(controls, fg_color="transparent")
        volume_row.pack(pady=(8, 0), fill="x")
        ctk.CTkLabel(volume_row, text="", image=volume_icon(16, theme.TEXT_SECONDARY), width=20).pack(side="left")
        self.volume_slider = ctk.CTkSlider(
            volume_row, from_=0, to=100, number_of_steps=100, command=self._on_volume_change,
            progress_color=theme.ACCENT, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
            fg_color=theme.BUTTON_NEUTRAL,
        )
        self.volume_slider.set(self.config_store.volume * 100)
        self.volume_slider.pack(side="left", fill="x", expand=True, padx=(8, 0))

    # ------------------------------------------------------------- scanning
    def rescan(self):
        if self._scanning:
            return
        folders = self.config_store.folders
        if not folders:
            self.status_label.configure(text=t(self.lang, "no_folders"))
            self._on_scan_complete([])
            return
        self._scanning = True
        self.status_label.configure(text=t(self.lang, "scanning"))
        language = self.lang

        def work():
            stations, empty_mod_names = scan_folders_detailed([Path(f) for f in folders], language)
            self.after(0, lambda: self._on_scan_complete(stations, empty_mod_names))

        threading.Thread(target=work, daemon=True).start()

    def _on_scan_complete(self, stations: list[Station], empty_mod_names: list[str] = ()):
        self._scanning = False
        self.stations = stations
        total_tracks = sum(s.track_count for s in stations)
        if stations:
            status = t(self.lang, "stations_summary", count=len(stations), tracks=total_tracks)
            if empty_mod_names:
                status += t(self.lang, "more_empty_mods", count=len(empty_mod_names))
            self.status_label.configure(text=status)
        elif empty_mod_names:
            names = ", ".join(empty_mod_names[:3])
            if len(empty_mod_names) > 3:
                names += f", +{len(empty_mod_names) - 3} more"
            self.status_label.configure(text=t(self.lang, "found_empty_mods", names=names))
        elif self.config_store.folders:
            self.status_label.configure(text=t(self.lang, "no_mod_found"))
        self._rebuild_station_list()
        self._refresh_track_list()

        # Read every track's length up front so the list shows real times
        # instead of '--:--' without waiting for playback. This is done in
        # small chunks on the main thread via `after`, NOT a background
        # thread: a ThreadPoolExecutor here reliably triggered a fatal,
        # unrecoverable interpreter crash (GIL corruption) when running
        # concurrently with pygame's mixer + the Tk mainloop. Chunking
        # keeps each pause imperceptible even for large mods.
        self._duration_backlog = [track for s in stations for track in s.tracks if track.duration is None]
        if self._duration_backlog:
            self.after(50, self._process_duration_backlog)

    def _process_duration_backlog(self):
        batch, self._duration_backlog = self._duration_backlog[:5], self._duration_backlog[5:]
        for track in batch:
            compute_track_duration(track)
            self.track_list_view.update_track_duration(track)
        if self._duration_backlog:
            self.after(15, self._process_duration_backlog)

    def _open_folder_manager(self):
        FolderManagerDialog(self, self.config_store, on_change=self.rescan, lang=self.lang)

    # ------------------------------------------------------------- search
    def _schedule_search_refresh(self):
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(180, self._run_scheduled_search_refresh)

    def _run_scheduled_search_refresh(self):
        self._search_after_id = None
        self._refresh_track_list()

    # ------------------------------------------------------------ stations
    def _rebuild_station_list(self):
        for child in self.stations_scroll.winfo_children():
            child.destroy()
        self.station_rows.clear()

        valid_keys = {s.key for s in self.stations}
        if self.selected_station_key not in valid_keys:
            self.selected_station_key = None

        for station in self.stations:
            enabled = station.key not in self.config_store.disabled_station_keys
            row = StationRow(
                self.stations_scroll, station, enabled,
                on_toggle=self._on_station_toggle, on_select=self._select_station, lang=self.lang,
            )
            row.pack(fill="x", pady=4)
            row.set_selected(self.selected_station_key == station.key)
            self.station_rows[station.key] = row

        self.all_stations_row.configure(
            fg_color=theme.BG_ROW_SELECTED if self.selected_station_key is None else theme.BUTTON_NEUTRAL
        )

    def _on_station_toggle(self, station_key: str, enabled: bool):
        self.config_store.set_station_enabled(station_key, enabled)
        self._refresh_track_list()

    def _select_station(self, station_key: Optional[str]):
        self.selected_station_key = station_key
        for key, row in self.station_rows.items():
            row.set_selected(key == station_key)
        self.all_stations_row.configure(
            fg_color=theme.BG_ROW_SELECTED if station_key is None else theme.BUTTON_NEUTRAL
        )
        self._refresh_track_list()

    # -------------------------------------------------------------- tracks
    def _visible_stations(self) -> list[Station]:
        # A disabled station's tracks never show up, whether browsing "All
        # Stations" or that station specifically - the checkbox is the
        # single source of truth for "will this station's music ever play".
        disabled = self.config_store.disabled_station_keys
        enabled_stations = [s for s in self.stations if s.key not in disabled]
        if self.selected_station_key is not None:
            return [s for s in enabled_stations if s.key == self.selected_station_key]
        return enabled_stations

    def _refresh_track_list(self):
        query = self.search_var.get().strip().lower()
        tracks: list[Track] = []
        for station in self._visible_stations():
            tracks.extend(station.tracks)
        if query:
            tracks = [
                t for t in tracks
                if query in t.display_name.lower()
                or query in t.mod_name.lower()
                or query in t.mod_author.lower()
                or query in t.station_name.lower()
            ]
        tracks.sort(key=lambda t: (t.station_name.lower(), t.display_name.lower()))
        self.current_display_tracks = tracks

        self.track_count_label.configure(text=t(self.lang, "tracks_header", count=len(tracks)))

        current = self.player.current_track
        current_path = current.file_path if current is not None else None
        if not tracks:
            self.track_list_view.set_tracks([], None)
            self.track_list_view.grid_remove()
            self.empty_tracks_label.grid()
            return

        self.empty_tracks_label.grid_remove()
        self.track_list_view.grid()
        self.track_list_view.set_tracks(tracks, current_path)

    def _play_all(self):
        if not self.current_display_tracks:
            return
        self._play_track(self.current_display_tracks[0])

    def _play_track(self, track: Track):
        self.player.set_queue(self.current_display_tracks, start_track=track)
        self.player.play()

    # ---------------------------------------------------------- transport
    def _toggle_play_pause(self):
        if self.player.current_track is None:
            self._play_all()
            return
        self.player.toggle_pause()

    def _on_volume_change(self, value: float):
        volume = value / 100.0
        self.player.set_volume(volume)
        self.config_store.volume = volume

    # ------------------------------------------------------------ callbacks
    def _on_track_change(self, track: Optional[Track]):
        if track is None:
            self.now_title_label.configure(text=t(self.lang, "nothing_playing"))
            self.now_meta_label.configure(text="")
            self.now_icon_label.configure(image=get_icon_image(None, NOWPLAYING_ICON_SIZE))
            self.progress_bar.set(0)
            self.elapsed_label.configure(text="0:00")
            self.duration_label.configure(text="--:--")
        else:
            author = t(self.lang, "unknown_author") if track.mod_author == "Unknown" else track.mod_author
            self.now_title_label.configure(text=track.display_name)
            self.now_meta_label.configure(text=f"{track.mod_name}  •  {author}")
            self.now_icon_label.configure(
                image=get_icon_image(track.mod_icon, NOWPLAYING_ICON_SIZE)
            )
            if track.duration is None:
                # Small delay so this never competes with the audio engine
                # actually starting playback; runs on the main thread.
                self.after(30, lambda tr=track: self._maybe_fetch_duration(tr))
        self.track_list_view.set_playing(track.file_path if track is not None else None)

    def _maybe_fetch_duration(self, track: Track):
        if self.player.current_track is not track:
            return
        compute_track_duration(track)

    def _on_playback_state_change(self, playing: bool):
        icon = pause_icon(18, theme.ACCENT_TEXT) if playing else play_icon(18, theme.ACCENT_TEXT)
        self.play_pause_btn.configure(image=icon)

    # ----------------------------------------------------------------- loop
    def _tick(self):
        self.player.poll_events()
        track = self.player.current_track
        if track is not None:
            duration = self.player.get_duration_seconds()
            position = self.player.get_position_seconds()
            self.elapsed_label.configure(text=format_time(position))
            self.duration_label.configure(text=format_time(duration))
            if duration and not self._seeking:
                self.progress_bar.set(min(1.0, position / duration))
            icon = pause_icon(18, theme.ACCENT_TEXT) if self.player.is_playing else play_icon(18, theme.ACCENT_TEXT)
            self.play_pause_btn.configure(image=icon)
        self.after(250, self._tick)

    # ------------------------------------------------------------- seeking
    def _on_seek_start(self, _event):
        self._seeking = True

    def _on_seek_drag(self, value: float):
        # Also covers the plain-click case: CTkSlider fires its `command`
        # for the initial click before our own ButtonPress binding runs
        # (see bind() override in customtkinter's CTkSlider), so treat any
        # drag/click callback as "seeking in progress" rather than relying
        # on binding order.
        self._seeking = True
        if self.player.current_track is not None:
            duration = self.player.get_duration_seconds()
            if duration:
                self.elapsed_label.configure(text=format_time(value * duration))

    def _on_seek_end(self, _event):
        if self.player.current_track is not None:
            duration = self.player.get_duration_seconds()
            if duration:
                self.player.seek(self.progress_bar.get() * duration)
        self._seeking = False

    def _on_close(self):
        self.player.stop()
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
