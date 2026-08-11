"""
Scans user-supplied folders for Hearts of Iron IV mods and extracts music
track metadata straight from the real mod file structure, per the official
modding wiki (https://hoi4.paradoxwikis.com/Music_modding), cross-checked
against real published mods:

    <content_root>/music/**/*.asset        -> song DEFINITIONS:
                                               music = { name = "KEY" file = "x.ogg" volume = 0.65 }
    <content_root>/music/**/*.txt          -> station ASSIGNMENTS:
                                               music_station = "station_key"
                                               music = { song = "KEY" chance = { ... } }
    <content_root>/localisation/**/*.yml   -> song titles (by KEY) and station
                                               display names (by "station_key_TITLE")

A song is only ever defined once (in a .asset file, by `name`/`file`), then
referenced by `song = "KEY"` from one or more station-assignment .txt files.
Mods that don't use the station system just put `file =` directly alongside
`song =`/`name =` in the same block - that's supported too (see
parse_song_definitions), with all such songs grouped under a fallback
station named after the mod itself.

No extra/custom config files are required or read.

HOI4 mods are installed on disk in one of two real layouts, and both are
supported here:

  - Steam Workshop: the descriptor sits INSIDE the mod's own folder, named
    exactly `descriptor.mod`:
        <content_root>/descriptor.mod
        <content_root>/music/...

  - Local/manual installs (Documents/Paradox Interactive/Hearts of Iron IV/mod/):
    the descriptor is a SEPARATE sibling file with an arbitrary name, which
    points at the actual content folder via its `path=` field:
        mod/my_music_mod.mod        (descriptor; path="mod/my_music_mod")
        mod/my_music_mod/music/...  (content, referenced by path=)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .i18n import HOI4_LANGUAGE_TAG
from .models import Station, Track

AUDIO_EXTENSIONS = {".ogg", ".mp3", ".wav"}
MAX_DESCRIPTOR_SEARCH_DEPTH = 4

_COMMENT_RE = re.compile(r"#.*")
_BLOCK_START_RE_CACHE: dict[str, re.Pattern] = {}

_KEYVAL_RE = re.compile(
    r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^\s{}]+))'
)
_LOC_LINE_RE = re.compile(r'^\s*([A-Za-z0-9_.\'\-]+)\s*:\d*\s*"(.*)"\s*$')


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def _find_blocks(text: str, block_name: str) -> list[str]:
    """Return the raw contents of every `block_name = { ... }` block, with
    proper brace matching (handles nesting)."""
    pattern = _BLOCK_START_RE_CACHE.get(block_name)
    if pattern is None:
        pattern = re.compile(r"\b" + re.escape(block_name) + r"\s*=\s*{")
        _BLOCK_START_RE_CACHE[block_name] = pattern

    blocks = []
    for match in pattern.finditer(text):
        start = match.end()
        depth = 1
        i = start
        n = len(text)
        while i < n and depth > 0:
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        blocks.append(text[start : i - 1])
    return blocks


def _parse_flat_keyvals(text: str) -> dict[str, str]:
    """Parse simple top-level `key = "value"` / `key = value` pairs, skipping
    nested blocks entirely (used for descriptor.mod)."""
    text_no_blocks = re.sub(r"{[^{}]*}", "", text)
    result: dict[str, str] = {}
    for match in _KEYVAL_RE.finditer(text_no_blocks):
        key = match.group(1)
        value = match.group(2) if match.group(2) is not None else match.group(3)
        if key not in result:
            result[key] = value
    return result


def _resolve_local_mod_content_root(mod_file: Path, path_value: str) -> Optional[Path]:
    """Resolve a standalone `<name>.mod` descriptor's `path=` field to the
    actual content folder. In practice that folder is always a sibling of
    the .mod file itself (e.g. mod/my_mod.mod + mod/my_mod/), regardless of
    whether path= is "mod/my_mod", "my_mod", or uses backslashes."""
    if not path_value:
        return None
    normalized = path_value.replace("\\", "/").strip().rstrip("/")
    folder_name = normalized.rsplit("/", 1)[-1]
    if not folder_name:
        return None
    candidate = mod_file.parent / folder_name
    return candidate if candidate.is_dir() else None


def find_mod_entries(base_dir: Path) -> list[tuple[Path, Path]]:
    """Find every mod under base_dir. Returns (descriptor_path, content_root)
    pairs, covering both the Steam Workshop layout (descriptor.mod inside the
    mod's own folder) and the local/manual-install layout (a standalone
    <name>.mod sitting next to a sibling content folder). Searched
    recursively up to a depth limit, so pointing this at a Steam Workshop
    content/<appid>/ folder or a HOI4 mod/ folder both work."""
    base_dir = Path(base_dir)
    entries: list[tuple[Path, Path]] = []
    seen_content_roots: set[Path] = set()

    def _add(descriptor_path: Path, content_root: Path):
        resolved = content_root.resolve()
        if resolved not in seen_content_roots:
            seen_content_roots.add(resolved)
            entries.append((descriptor_path, content_root))

    def _walk(directory: Path, depth: int):
        workshop_descriptor = directory / "descriptor.mod"
        if workshop_descriptor.is_file():
            _add(workshop_descriptor, directory)
            return  # a mod's own content folder isn't searched for more mods

        try:
            loose_mod_files = [p for p in directory.glob("*.mod") if p.is_file()]
        except OSError:
            loose_mod_files = []
        for mod_file in loose_mod_files:
            descriptor = parse_descriptor(mod_file)
            content_root = _resolve_local_mod_content_root(mod_file, descriptor.get("path", ""))
            if content_root is not None:
                _add(mod_file, content_root)

        if depth >= MAX_DESCRIPTOR_SEARCH_DEPTH:
            return
        try:
            subdirs = [p for p in directory.iterdir() if p.is_dir()]
        except OSError:
            return
        for subdir in subdirs:
            _walk(subdir, depth + 1)

    _walk(base_dir, 0)
    return entries


def parse_descriptor(descriptor_path: Path) -> dict:
    try:
        text = descriptor_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return {}
    text = _strip_comments(text)
    return _parse_flat_keyvals(text)


def _unescape(value: str) -> str:
    return value.replace('\\"', '"').replace("\\n", "\n")


def parse_localisation(content_root: Path, language: str = "en") -> dict[str, str]:
    """Parse every localisation/**/*.yml file and return song/station key ->
    display text, preferring `language` (falling back to English, then to
    whatever else is available, per key - not per file - so a mod that's
    only partially translated doesn't lose the untranslated entries)."""
    loc_dir = content_root / "localisation"
    if not loc_dir.is_dir():
        return {}

    preferred_tag = HOI4_LANGUAGE_TAG.get(language, "l_english")

    def priority(path: Path) -> int:
        if preferred_tag in path.name:
            return 2
        if "l_english" in path.name:
            return 1
        return 0

    # Ascending priority order: each subsequent file's keys overwrite
    # earlier ones, so the highest-priority source available for a given
    # key always wins, independently per key.
    yml_files = sorted(loc_dir.rglob("*.yml"), key=priority)

    result: dict[str, str] = {}
    for yml_path in yml_files:
        try:
            text = yml_path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if line.strip().startswith("#"):
                continue
            match = _LOC_LINE_RE.match(line)
            if not match:
                continue
            key, value = match.group(1), match.group(2)
            result[key] = _unescape(value)
    return result


def _build_music_file_index(content_root: Path) -> dict[str, Path]:
    """Maps every filename under music/ to its full path, in one pass. The
    real .asset format's `file =` is just a bare filename with no
    directory (tracks live in per-station subfolders), so this fallback
    lookup is needed for essentially every track - doing it as a fresh
    rglob() per track instead of once per mod turned a few thousand tracks
    into tens of millions of filesystem stats and effectively hung the app."""
    music_dir = content_root / "music"
    index: dict[str, Path] = {}
    if not music_dir.is_dir():
        return index
    for path in music_dir.rglob("*"):
        if path.is_file():
            index.setdefault(path.name, path)
    return index


def _resolve_audio_path(content_root: Path, raw_path: str, file_index: dict[str, Path]) -> Optional[Path]:
    raw_path = raw_path.replace("\\", "/").strip()
    candidate = content_root / raw_path
    if candidate.is_file():
        return candidate

    # Some mods reference files relative to the mod root without the
    # "music/" prefix matching the actual folder casing/layout, or (the
    # common case for the real .asset format) with no directory at all -
    # fall back to the precomputed basename index instead of rescanning.
    return file_index.get(Path(raw_path).name)


def parse_song_definitions(content_root: Path) -> dict[str, dict]:
    """Song DEFINITIONS: real mods put these in `*.asset` files using
    `name = "KEY"`, but some simpler mods skip .asset entirely and put
    `song = "KEY"` + `file = "..."` directly together in one .txt block -
    both are accepted here. A block only counts as a definition if it has
    a `file =` field; blocks with just `song =` (and no `file =`) are
    station ASSIGNMENTS instead (see parse_station_assignments) and are
    intentionally skipped here.
    Returns song_key -> {"file": str, "volume": float}."""
    music_dir = content_root / "music"
    definitions: dict[str, dict] = {}
    if not music_dir.is_dir():
        return definitions

    paths = sorted(music_dir.rglob("*.asset")) + sorted(music_dir.rglob("*.txt"))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        text = _strip_comments(text)
        for block in _find_blocks(text, "music"):
            file_match = re.search(r'file\s*=\s*"([^"]*)"', block)
            if not file_match:
                continue
            name_match = re.search(r'(?:name|song)\s*=\s*"([^"]*)"', block)
            if not name_match:
                continue
            volume_match = re.search(r"volume\s*=\s*([\d.]+)", block)
            definitions.setdefault(
                name_match.group(1),
                {
                    "file": file_match.group(1),
                    "volume": float(volume_match.group(1)) if volume_match else 1.0,
                },
            )
    return definitions


_STATION_DECL_RE = re.compile(r'music_station\s*=\s*"?([A-Za-z0-9_\-\.]+)"?')


def parse_station_assignments(content_root: Path) -> dict[str, list[str]]:
    """Station ASSIGNMENTS: `*.txt` files under music/ that declare
    `music_station = "station_key"`, followed by `music = { song = "KEY"
    chance = {...} }` blocks referencing songs by the name they were given
    in a .asset file. Returns station_key -> [song_key, ...].

    Handles a file declaring `music_station` more than once (some mods
    assign several stations from a single file) by treating each
    declaration as starting a new segment that runs until the next
    declaration - everything between them belongs to that station. Also
    accepts an unquoted station key (`music_station = gunka`), since not
    every mod follows the quoted-string convention from the wiki example."""
    music_dir = content_root / "music"
    assignments: dict[str, list[str]] = {}
    if not music_dir.is_dir():
        return assignments

    for txt_path in sorted(music_dir.rglob("*.txt")):
        try:
            text = txt_path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        text = _strip_comments(text)
        declarations = list(_STATION_DECL_RE.finditer(text))
        if not declarations:
            continue
        for i, decl in enumerate(declarations):
            station_key = decl.group(1)
            segment_end = declarations[i + 1].start() if i + 1 < len(declarations) else len(text)
            segment = text[decl.end():segment_end]
            song_keys = [
                m.group(1)
                for block in _find_blocks(segment, "music")
                for m in [re.search(r'song\s*=\s*"([^"]*)"', block)]
                if m
            ]
            if song_keys:
                assignments.setdefault(station_key, []).extend(song_keys)
    return assignments


def _station_display_name(localisation: dict[str, str], station_key: str) -> str:
    for candidate in (f"{station_key}_TITLE", station_key, f"{station_key}_NAME"):
        if candidate in localisation:
            return localisation[candidate]
    # Case-insensitive fallback - some mods aren't consistent about casing
    # between the station key and its localisation entry.
    lower_key = station_key.lower()
    wanted = {f"{lower_key}_title", lower_key, f"{lower_key}_name"}
    for loc_key, value in localisation.items():
        if loc_key.lower() in wanted:
            return value
    return station_key.replace("_", " ").replace("-", " ").strip().title() or station_key


def _guess_author(descriptor: dict, mod_root: Path) -> str:
    for key in ("author", "authors", "creator", "credit", "credits"):
        if key in descriptor and descriptor[key].strip():
            return descriptor[key].strip()

    # A handful of mods embed the author in a top-level text file.
    for filename in ("author.txt", "credits.txt", "AUTHOR.txt"):
        candidate = mod_root / filename
        if candidate.is_file():
            try:
                content = candidate.read_text(encoding="utf-8", errors="replace").strip()
                if content:
                    return content.splitlines()[0].strip()
            except OSError:
                pass

    return "Unknown"


def _resolve_mod_icon(descriptor: dict, descriptor_path: Path, content_root: Path) -> Optional[Path]:
    picture_name = descriptor.get("picture")
    if picture_name:
        for base in (content_root, descriptor_path.parent):
            candidate = base / picture_name
            if candidate.is_file():
                return candidate
    for fallback in ("thumbnail.png", "thumbnail.jpg"):
        candidate = content_root / fallback
        if candidate.is_file():
            return candidate
    return None


def load_stations(descriptor_path: Path, content_root: Path, language: str = "en") -> list[Station]:
    """Build every Station for one mod: real stations from music_station
    assignments, plus a fallback station (named after the mod) for any
    defined songs that were never assigned to a station."""
    descriptor = parse_descriptor(descriptor_path)
    mod_name = descriptor.get("name", content_root.name).strip() or content_root.name
    author = _guess_author(descriptor, content_root)
    icon = _resolve_mod_icon(descriptor, descriptor_path, content_root)
    mod_id = str(content_root.resolve())

    localisation = parse_localisation(content_root, language)
    definitions = parse_song_definitions(content_root)
    assignments = parse_station_assignments(content_root)
    file_index = _build_music_file_index(content_root)

    def build_track(song_key: str, station_name: str) -> Optional[Track]:
        definition = definitions.get(song_key)
        if definition is None:
            return None
        resolved = _resolve_audio_path(content_root, definition["file"], file_index)
        if resolved is None or resolved.suffix.lower() not in AUDIO_EXTENSIONS:
            return None
        return Track(
            song_key=song_key,
            title=localisation.get(song_key, song_key),
            file_path=resolved,
            mod_name=mod_name,
            mod_author=author,
            mod_id=mod_id,
            station_name=station_name,
            mod_icon=icon,
            volume=definition["volume"],
        )

    stations: list[Station] = []
    assigned_song_keys: set[str] = set()

    for station_key, song_keys in assignments.items():
        station_name = _station_display_name(localisation, station_key)
        station = Station(
            key=f"{mod_id}::{station_key}", name=station_name,
            mod_name=mod_name, mod_author=author, mod_icon=icon,
        )
        seen_files: set[str] = set()
        for song_key in song_keys:
            assigned_song_keys.add(song_key)
            track = build_track(song_key, station_name)
            if track is None:
                continue
            file_key = str(track.file_path.resolve())
            if file_key in seen_files:
                continue
            seen_files.add(file_key)
            station.tracks.append(track)
        if station.tracks:
            station.tracks.sort(key=lambda t: t.title.lower())
            stations.append(station)

    leftover_keys = sorted(k for k in definitions if k not in assigned_song_keys)
    if leftover_keys:
        fallback = Station(
            key=f"{mod_id}::__default__", name=mod_name,
            mod_name=mod_name, mod_author=author, mod_icon=icon,
        )
        seen_files = set()
        for song_key in leftover_keys:
            track = build_track(song_key, mod_name)
            if track is None:
                continue
            file_key = str(track.file_path.resolve())
            if file_key in seen_files:
                continue
            seen_files.add(file_key)
            fallback.tracks.append(track)
        if fallback.tracks:
            fallback.tracks.sort(key=lambda t: t.title.lower())
            stations.append(fallback)

    stations.sort(key=lambda s: s.name.lower())
    return stations


def scan_folders_detailed(folders: list[Path], language: str = "en") -> tuple[list[Station], list[str]]:
    """Like scan_folders, but also reports mods that were found (had a valid
    descriptor) but contributed zero stations/tracks - useful for telling
    "nothing detected at all" apart from "found your mod, but couldn't
    parse its music/ files", which otherwise look identical to the user."""
    stations_by_key: dict[str, Station] = {}
    empty_mod_names: list[str] = []
    for folder in folders:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for descriptor_path, content_root in find_mod_entries(folder):
            stations = load_stations(descriptor_path, content_root, language)
            if not stations:
                descriptor = parse_descriptor(descriptor_path)
                empty_mod_names.append(descriptor.get("name", content_root.name).strip() or content_root.name)
                continue
            for station in stations:
                stations_by_key[station.key] = station
    result = sorted(stations_by_key.values(), key=lambda s: s.name.lower())
    return result, empty_mod_names


def scan_folders(folders: list[Path], language: str = "en") -> list[Station]:
    """Scan every supplied folder for HOI4 music mods and return every
    Station found (deduplicated by station key)."""
    stations, _empty = scan_folders_detailed(folders, language)
    return stations
