"""Data models for mods and tracks."""
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
    mod_icon: Optional[Path] = None
    volume: float = 1.0
    duration: Optional[float] = None

    @property
    def display_name(self) -> str:
        return self.title or self.song_key


@dataclass
class Mod:
    mod_id: str
    name: str
    author: str
    root: Path
    icon: Optional[Path] = None
    tracks: list[Track] = field(default_factory=list)

    @property
    def track_count(self) -> int:
        return len(self.tracks)
