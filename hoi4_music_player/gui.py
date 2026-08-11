"""CustomTkinter-based UI for the HOI4 Music Player."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from tkinter import filedialog

from . import theme
from .config import Config
from .duration import compute_track_duration
from .icons import (
    folder_icon,
    next_icon,
    pause_icon,
    play_icon,
    previous_icon,
    refresh_icon,
    volume_icon,
)
from .mod_scanner import scan_folders
from .models import Mod, Track
from .player_engine import PlayerEngine
from .utils import format_time, get_icon_image

ctk.set_appearance_mode("dark")

SIDEBAR_ICON_SIZE = 40
TRACK_ICON_SIZE = 36
NOWPLAYING_ICON_SIZE = 56
SIDEBAR_WIDTH = 320

_ROW_COLORS = {
    "normal": theme.BG_ROW,
    "hover": theme.BG_ROW_HOVER,
    "selected": theme.BG_ROW_SELECTED,
    "playing": theme.BG_ROW_PLAYING,
}


# Static wrap widths for row labels, rather than clipping long names. A
# dynamic (per-resize) wraplength and a resizable sidebar were both tried
# and reverted - see gui.py history/README - reconfiguring widget geometry
# on every pixel of drag/resize motion made customtkinter's canvas redraw
# fall behind and leave visible artifacts on screen. A long mod or track
# name just wraps onto a second or third line instead.
SIDEBAR_LABEL_WRAP = 230
TRACK_LABEL_WRAP = 420


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


class ModRow(_HoverRow):
    def __init__(self, master, mod: Mod, enabled: bool, on_toggle, on_select):
        super().__init__(master)
        self.mod = mod
        self.on_select = on_select

        self.grid_columnconfigure(2, weight=1)

        self.checkbox_var = ctk.BooleanVar(value=enabled)
        checkbox = ctk.CTkCheckBox(
            self, text="", variable=self.checkbox_var, width=20,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            checkmark_color=theme.ACCENT_TEXT, border_color=theme.TEXT_MUTED,
            command=lambda: on_toggle(mod.mod_id, self.checkbox_var.get()),
        )
        checkbox.grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=8)

        icon_label = ctk.CTkLabel(self, text="", image=get_icon_image(mod.icon, SIDEBAR_ICON_SIZE))
        icon_label.grid(row=0, column=1, rowspan=2, padx=(2, 10), pady=8)

        name_label = ctk.CTkLabel(
            self, text=mod.name, anchor="w", text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(weight="bold"), wraplength=SIDEBAR_LABEL_WRAP, justify="left",
        )
        name_label.grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=(8, 0))

        subtitle = f"{mod.author} • {mod.track_count} tracks"
        sub_label = ctk.CTkLabel(
            self, text=subtitle, anchor="w", font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY, wraplength=SIDEBAR_LABEL_WRAP, justify="left",
        )
        sub_label.grid(row=1, column=2, sticky="ew", padx=(0, 10), pady=(0, 8))

        for widget in (self, icon_label, name_label, sub_label):
            widget.bind("<Button-1>", lambda e: self.on_select(mod.mod_id))
            self._bind_hover(widget)

    def set_selected(self, selected: bool):
        self.set_state("selected" if selected else "normal")


class TrackRow(_HoverRow):
    def __init__(self, master, track: Track, on_play):
        super().__init__(master)
        self.track = track

        self.grid_columnconfigure(1, weight=3)
        self.grid_columnconfigure(2, weight=2)

        icon_label = ctk.CTkLabel(
            self, text="", image=get_icon_image(track.mod_icon, TRACK_ICON_SIZE)
        )
        icon_label.grid(row=0, column=0, rowspan=2, padx=(8, 10), pady=8)

        title_label = ctk.CTkLabel(
            self, text=track.display_name, anchor="w", text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(weight="bold"), wraplength=TRACK_LABEL_WRAP, justify="left",
        )
        title_label.grid(row=0, column=1, sticky="ew", pady=(8, 0))

        mod_label = ctk.CTkLabel(
            self, text=f"{track.mod_name}  •  {track.mod_author}", anchor="w",
            font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY,
            wraplength=TRACK_LABEL_WRAP, justify="left",
        )
        mod_label.grid(row=1, column=1, sticky="ew", pady=(0, 8))

        duration_label = ctk.CTkLabel(
            self, text=format_time(track.duration), anchor="e", width=50,
            text_color=theme.TEXT_SECONDARY,
        )
        duration_label.grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 12))

        play_btn = ctk.CTkButton(
            self, text="", image=play_icon(16, theme.ACCENT_TEXT), width=32, height=32,
            corner_radius=6, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=lambda: on_play(track),
        )
        play_btn.grid(row=0, column=3, rowspan=2, padx=(0, 10))

        for widget in (self, icon_label, title_label, mod_label, duration_label):
            widget.bind("<Double-Button-1>", lambda e: on_play(track))
            self._bind_hover(widget)

    def set_playing(self, playing: bool):
        self.set_state("playing" if playing else "normal")


def _styled_button(master, **kwargs):
    defaults = dict(
        fg_color=theme.BUTTON_NEUTRAL, hover_color=theme.BUTTON_NEUTRAL_HOVER,
        text_color=theme.TEXT_PRIMARY, corner_radius=8,
    )
    defaults.update(kwargs)
    return ctk.CTkButton(master, **defaults)


class FolderManagerDialog(ctk.CTkToplevel):
    def __init__(self, master, config_store: Config, on_change):
        super().__init__(master)
        self.title("Manage Mod Folders")
        self.geometry("580x380")
        self.configure(fg_color=theme.BG_APP)
        self.config_store = config_store
        self.on_change = on_change
        self.transient(master)

        ctk.CTkLabel(
            self,
            text="Add the folders where your HOI4 music mods live\n"
                 "(a Steam Workshop content folder, or your own mods directory).",
            justify="left", text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=18, pady=(18, 10))

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=theme.BG_PANEL, label_text="")
        self.list_frame.pack(fill="both", expand=True, padx=18, pady=8)

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=18, pady=(0, 18))
        _styled_button(
            button_row, text="  Add Folder…", image=folder_icon(16, theme.TEXT_PRIMARY),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, text_color=theme.ACCENT_TEXT,
            command=self._add_folder,
        ).pack(side="left")
        _styled_button(button_row, text="Close", command=self.destroy).pack(side="right")

        self._refresh_list()

    def _refresh_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        folders = self.config_store.folders
        if not folders:
            ctk.CTkLabel(self.list_frame, text="No folders added yet.", text_color=theme.TEXT_SECONDARY).pack(pady=8)
        for folder in folders:
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=folder, anchor="w", text_color=theme.TEXT_PRIMARY).pack(
                side="left", fill="x", expand=True
            )
            _styled_button(
                row, text="Remove", width=76, fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
                command=lambda f=folder: self._remove_folder(f),
            ).pack(side="right")

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select a folder containing HOI4 mods")
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
        self.title("HOI4 Music Player")
        self.geometry("1080x700")
        self.minsize(880, 580)
        self.configure(fg_color=theme.BG_APP)

        self.config_store = Config()
        self.player = PlayerEngine()
        self.player.volume = self.config_store.volume
        self.player.on_track_change = self._on_track_change
        self.player.on_playback_state_change = self._on_playback_state_change

        self.mods: list[Mod] = []
        self.mod_rows: dict[str, ModRow] = {}
        self.track_rows: list[TrackRow] = []
        self.selected_mod_id: Optional[str] = None
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
        ctk.CTkLabel(
            brand, text="HOI4 Music Player", font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        _styled_button(
            top_bar, text="  Manage Folders…", image=folder_icon(16, theme.TEXT_PRIMARY),
            command=self._open_folder_manager,
        ).pack(side="left", padx=(0, 8), pady=10)
        _styled_button(
            top_bar, text="", image=refresh_icon(16, theme.TEXT_PRIMARY), width=36,
            command=self.rescan,
        ).pack(side="left", pady=10)

        self.status_label = ctk.CTkLabel(top_bar, text="", text_color=theme.TEXT_SECONDARY)
        self.status_label.pack(side="left", padx=14)

        search_entry = ctk.CTkEntry(
            top_bar, placeholder_text="Search tracks, mods, authors…",
            textvariable=self.search_var, width=260, fg_color=theme.BG_ROW,
            border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY,
        )
        search_entry.pack(side="right", padx=16, pady=10)

        # Sidebar (mods). Fixed width - a live drag-to-resize handle was
        # tried and reverted: CTkFrame's canvas redraw couldn't keep up
        # with rapid <B1-Motion> events and left visible ghost artifacts on
        # screen. Long mod names just wrap onto extra lines instead (see
        # SIDEBAR_LABEL_WRAP), so a fixed width doesn't clip anything.
        self.sidebar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=theme.BG_SIDEBAR)
        self.sidebar.grid(row=1, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(
            self.sidebar, text="MODS", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=16, pady=(16, 6))
        self.all_mods_row = _styled_button(
            self.sidebar, text="All Mods", anchor="w",
            fg_color=theme.BG_ROW_SELECTED, hover_color=theme.BG_ROW_HOVER,
            command=lambda: self._select_mod(None),
        )
        self.all_mods_row.pack(fill="x", padx=14, pady=(0, 10))

        self.mods_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", label_text="")
        self.mods_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Track list
        track_panel = ctk.CTkFrame(self, corner_radius=0, fg_color=theme.BG_PANEL)
        track_panel.grid(row=1, column=1, sticky="nsew")
        track_panel.grid_rowconfigure(1, weight=1)
        track_panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(track_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.track_count_label = ctk.CTkLabel(
            header, text="Tracks", font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.track_count_label.pack(side="left")
        _styled_button(
            header, text="  Play All", image=play_icon(14, theme.ACCENT_TEXT), width=110,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, text_color=theme.ACCENT_TEXT,
            command=self._play_all,
        ).pack(side="right")

        self.tracks_scroll = ctk.CTkScrollableFrame(track_panel, fg_color="transparent", label_text="")
        self.tracks_scroll.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))

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
            bar, text="Nothing playing", anchor="w", font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.now_title_label.grid(row=0, column=1, sticky="ew", padx=8, pady=(12, 0))

        self.now_meta_label = ctk.CTkLabel(
            bar, text="Add a mod folder to get started", anchor="w",
            text_color=theme.TEXT_SECONDARY,
        )
        self.now_meta_label.grid(row=1, column=1, sticky="ew", padx=8)

        progress_row = ctk.CTkFrame(bar, fg_color="transparent")
        progress_row.grid(row=2, column=1, sticky="ew", padx=8, pady=(4, 10))
        progress_row.grid_columnconfigure(1, weight=1)
        self.elapsed_label = ctk.CTkLabel(progress_row, text="0:00", width=40, text_color=theme.TEXT_SECONDARY)
        self.elapsed_label.grid(row=0, column=0)
        self.progress_bar = ctk.CTkProgressBar(
            progress_row, progress_color=theme.ACCENT, fg_color=theme.BUTTON_NEUTRAL,
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=10)
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
            self.status_label.configure(text="No folders added — click 'Manage Folders…'")
            self._on_scan_complete([])
            return
        self._scanning = True
        self.status_label.configure(text="Scanning…")

        def work():
            mods = scan_folders([Path(f) for f in folders])
            self.after(0, lambda: self._on_scan_complete(mods))

        threading.Thread(target=work, daemon=True).start()

    def _on_scan_complete(self, mods: list[Mod]):
        self._scanning = False
        self.mods = mods
        total_tracks = sum(m.track_count for m in mods)
        if mods:
            self.status_label.configure(text=f"{len(mods)} mods, {total_tracks} tracks")
        elif self.config_store.folders:
            self.status_label.configure(text="No music mods found in the added folders")
        self._rebuild_mod_list()
        self._refresh_track_list()

        # Read every track's length up front so the list shows real times
        # instead of '--:--' without waiting for playback. This is done in
        # small chunks on the main thread via `after`, NOT a background
        # thread: a ThreadPoolExecutor here reliably triggered a fatal,
        # unrecoverable interpreter crash (GIL corruption) when running
        # concurrently with pygame's mixer + the Tk mainloop. Chunking
        # keeps each pause imperceptible even for large mods.
        self._duration_backlog = [t for m in mods for t in m.tracks if t.duration is None]
        if self._duration_backlog:
            self.after(50, self._process_duration_backlog)

    def _process_duration_backlog(self):
        batch, self._duration_backlog = self._duration_backlog[:5], self._duration_backlog[5:]
        for track in batch:
            compute_track_duration(track)
        if self._duration_backlog:
            self.after(15, self._process_duration_backlog)
        else:
            self._refresh_track_list()

    def _open_folder_manager(self):
        FolderManagerDialog(self, self.config_store, on_change=self.rescan)

    # ------------------------------------------------------------- search
    def _schedule_search_refresh(self):
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(180, self._run_scheduled_search_refresh)

    def _run_scheduled_search_refresh(self):
        self._search_after_id = None
        self._refresh_track_list()

    # ---------------------------------------------------------------- mods
    def _rebuild_mod_list(self):
        for child in self.mods_scroll.winfo_children():
            child.destroy()
        self.mod_rows.clear()

        valid_ids = {m.mod_id for m in self.mods}
        if self.selected_mod_id not in valid_ids:
            self.selected_mod_id = None

        for mod in self.mods:
            enabled = mod.mod_id not in self.config_store.disabled_mod_ids
            row = ModRow(
                self.mods_scroll, mod, enabled,
                on_toggle=self._on_mod_toggle, on_select=self._select_mod,
            )
            row.pack(fill="x", pady=4)
            row.set_selected(self.selected_mod_id == mod.mod_id)
            self.mod_rows[mod.mod_id] = row

        self.all_mods_row.configure(
            fg_color=theme.BG_ROW_SELECTED if self.selected_mod_id is None else theme.BUTTON_NEUTRAL
        )

    def _on_mod_toggle(self, mod_id: str, enabled: bool):
        self.config_store.set_mod_enabled(mod_id, enabled)
        self._refresh_track_list()

    def _select_mod(self, mod_id: Optional[str]):
        self.selected_mod_id = mod_id
        for mid, row in self.mod_rows.items():
            row.set_selected(mid == mod_id)
        self.all_mods_row.configure(
            fg_color=theme.BG_ROW_SELECTED if mod_id is None else theme.BUTTON_NEUTRAL
        )
        self._refresh_track_list()

    # -------------------------------------------------------------- tracks
    def _visible_mods(self) -> list[Mod]:
        # A disabled mod's tracks never show up, whether browsing "All
        # Mods" or that mod specifically - the checkbox is the single
        # source of truth for "will this mod's music ever play".
        disabled = self.config_store.disabled_mod_ids
        enabled_mods = [m for m in self.mods if m.mod_id not in disabled]
        if self.selected_mod_id is not None:
            return [m for m in enabled_mods if m.mod_id == self.selected_mod_id]
        return enabled_mods

    def _refresh_track_list(self):
        for child in self.tracks_scroll.winfo_children():
            child.destroy()
        self.track_rows.clear()

        query = self.search_var.get().strip().lower()
        tracks: list[Track] = []
        for mod in self._visible_mods():
            tracks.extend(mod.tracks)
        if query:
            tracks = [
                t for t in tracks
                if query in t.display_name.lower()
                or query in t.mod_name.lower()
                or query in t.mod_author.lower()
            ]
        tracks.sort(key=lambda t: (t.mod_name.lower(), t.display_name.lower()))
        self.current_display_tracks = tracks

        self.track_count_label.configure(text=f"Tracks ({len(tracks)})")

        current = self.player.current_track
        if not tracks:
            ctk.CTkLabel(
                self.tracks_scroll,
                text="No tracks to show. Add folders with HOI4 music mods, "
                     "or adjust your search/filters.",
                wraplength=520, justify="left", text_color=theme.TEXT_SECONDARY,
            ).pack(pady=16, padx=8, anchor="w")
            return

        for track in tracks:
            row = TrackRow(self.tracks_scroll, track, on_play=self._play_track)
            row.pack(fill="x", pady=3)
            row.set_playing(current is not None and current.file_path == track.file_path)
            self.track_rows.append(row)

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
            self.now_title_label.configure(text="Nothing playing")
            self.now_meta_label.configure(text="")
            self.now_icon_label.configure(image=get_icon_image(None, NOWPLAYING_ICON_SIZE))
            self.progress_bar.set(0)
            self.elapsed_label.configure(text="0:00")
            self.duration_label.configure(text="--:--")
        else:
            self.now_title_label.configure(text=track.display_name)
            self.now_meta_label.configure(text=f"{track.mod_name}  •  {track.mod_author}")
            self.now_icon_label.configure(
                image=get_icon_image(track.mod_icon, NOWPLAYING_ICON_SIZE)
            )
            if track.duration is None:
                # Small delay so this never competes with the audio engine
                # actually starting playback; runs on the main thread.
                self.after(30, lambda t=track: self._maybe_fetch_duration(t))
        for row in self.track_rows:
            row.set_playing(track is not None and row.track.file_path == track.file_path)

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
            if duration:
                self.progress_bar.set(min(1.0, position / duration))
            icon = pause_icon(18, theme.ACCENT_TEXT) if self.player.is_playing else play_icon(18, theme.ACCENT_TEXT)
            self.play_pause_btn.configure(image=icon)
        self.after(250, self._tick)

    def _on_close(self):
        self.player.stop()
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
