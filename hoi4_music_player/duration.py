"""Shared helper for reading a track's playback length via mutagen. Safe to
call from a worker thread - it only mutates the Track's own `duration`
field, which the GUI polls rather than being pushed updates for."""
from __future__ import annotations

try:
    from mutagen import File as _MutagenFile
except ImportError:  # pragma: no cover - mutagen is a listed dependency
    _MutagenFile = None


def compute_track_duration(track) -> None:
    if track.duration is not None or _MutagenFile is None:
        return
    try:
        audio = _MutagenFile(track.file_path)
        if audio is not None and audio.info is not None:
            track.duration = float(audio.info.length)
    except Exception:
        pass
