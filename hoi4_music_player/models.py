"""Data models for stations and tracks."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Track:
    song_key: str
    title: str
    file_path: Path
    mod_name: str
    mod_author: str
    mod_id: str
    station_name: str = ""
    mod_icon: Optional[Path] = None
    # Some mods embed a per-track album art reference (£sprite_name) in the
    # song's title localisation, resolved via interface/*.gfx - see
    # mod_scanner.parse_sprite_textures. Falls back to the mod's own icon
    # (mod_icon) when a track doesn't have one of its own.
    track_icon: Optional[Path] = None
    volume: float = 1.0
    duration: Optional[float] = None

    @property
    def display_name(self) -> str:
        return self.title or self.song_key

    @property
    def icon(self) -> Optional[Path]:
        return self.track_icon or self.mod_icon


@dataclass
class Station:
    """A radio station (music channel) as defined by a mod's
    `music_station = "..."` assignment files. Mods that don't use the
    station system at all get a single fallback station named after
    themselves, so every track always belongs to exactly one station."""

    key: str
    name: str
    mod_name: str
    mod_author: str
    mod_icon: Optional[Path] = None
    tracks: list[Track] = field(default_factory=list)

    @property
    def track_count(self) -> int:
        return len(self.tracks)
