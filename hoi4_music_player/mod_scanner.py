"""
Scans user-supplied folders for Hearts of Iron IV mods and extracts music
track metadata straight from the real mod file structure:

    <content_root>/music/**/*.txt          -> music = { song = "..." file = "..." volume = ... }
    <content_root>/localisation/**/*.yml   -> localisation of song keys -> display titles

No extra/custom config files are required or read. This mirrors the format
Paradox and mod authors actually ship music mods in.

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

from .models import Mod, Track

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


def parse_localisation(mod_root: Path) -> dict[str, str]:
    """Parse every localisation/**/*.yml file and return song_key -> title.
    Prefers English localisation when a key is defined in multiple languages."""
    loc_dir = mod_root / "localisation"
    if not loc_dir.is_dir():
        return {}

    result: dict[str, str] = {}
    english_keys: set[str] = set()

    yml_files = sorted(loc_dir.rglob("*.yml"))
    # Process english files last so they take priority (except keys already
    # marked as coming from an english file, which always win).
    yml_files.sort(key=lambda p: 0 if "l_english" in p.name else 1)

    for yml_path in yml_files:
        is_english = "l_english" in yml_path.name
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
            if key in english_keys:
                continue
            if key in result and not is_english:
                continue
            result[key] = _unescape(value)
            if is_english:
                english_keys.add(key)
    return result


def _resolve_audio_path(mod_root: Path, raw_path: str) -> Optional[Path]:
    raw_path = raw_path.replace("\\", "/").strip()
    candidate = mod_root / raw_path
    if candidate.is_file():
        return candidate

    # Some mods reference files relative to the mod root without the
    # "music/" prefix matching the actual folder casing/layout - fall back
    # to searching for the basename anywhere under music/.
    basename = Path(raw_path).name
    music_dir = mod_root / "music"
    if music_dir.is_dir():
        for match in music_dir.rglob(basename):
            if match.is_file():
                return match
    return None


def parse_music_tracks(mod_root: Path) -> list[dict]:
    music_dir = mod_root / "music"
    if not music_dir.is_dir():
        return []

    raw_tracks: list[dict] = []
    for txt_path in sorted(music_dir.rglob("*.txt")):
        try:
            text = txt_path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        text = _strip_comments(text)
        for block in _find_blocks(text, "music"):
            song_match = re.search(r'song\s*=\s*"([^"]*)"', block)
            file_match = re.search(r'file\s*=\s*"([^"]*)"', block)
            volume_match = re.search(r"volume\s*=\s*([\d.]+)", block)
            if not song_match or not file_match:
                continue
            raw_tracks.append(
                {
                    "song": song_match.group(1),
                    "file": file_match.group(1),
                    "volume": float(volume_match.group(1)) if volume_match else 1.0,
                }
            )
    return raw_tracks


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


def load_mod(descriptor_path: Path, content_root: Path) -> Optional[Mod]:
    descriptor = parse_descriptor(descriptor_path)
    name = descriptor.get("name", content_root.name).strip() or content_root.name
    author = _guess_author(descriptor, content_root)

    icon: Optional[Path] = None
    picture_name = descriptor.get("picture")
    if picture_name:
        for base in (content_root, descriptor_path.parent):
            candidate = base / picture_name
            if candidate.is_file():
                icon = candidate
                break
    if icon is None:
        for fallback in ("thumbnail.png", "thumbnail.jpg"):
            candidate = content_root / fallback
            if candidate.is_file():
                icon = candidate
                break

    localisation = parse_localisation(content_root)
    raw_tracks = parse_music_tracks(content_root)
    if not raw_tracks:
        return None

    mod_id = str(content_root.resolve())
    mod = Mod(mod_id=mod_id, name=name, author=author, root=content_root, icon=icon)

    seen_files: set[str] = set()
    for raw in raw_tracks:
        resolved = _resolve_audio_path(content_root, raw["file"])
        if resolved is None:
            continue
        if resolved.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        key = str(resolved.resolve())
        if key in seen_files:
            continue
        seen_files.add(key)

        song_key = raw["song"]
        title = localisation.get(song_key, song_key)
        mod.tracks.append(
            Track(
                song_key=song_key,
                title=title,
                file_path=resolved,
                mod_name=name,
                mod_author=author,
                mod_id=mod_id,
                mod_icon=icon,
                volume=raw["volume"],
            )
        )

    if not mod.tracks:
        return None
    mod.tracks.sort(key=lambda t: t.title.lower())
    return mod


def scan_folders_detailed(folders: list[Path]) -> tuple[list[Mod], list[str]]:
    """Like scan_folders, but also reports mods that were found (had a valid
    descriptor) but contributed zero tracks - useful for telling "nothing
    detected at all" apart from "found your mod, but couldn't parse its
    music/ files", which otherwise look identical to the user."""
    mods_by_id: dict[str, Mod] = {}
    empty_mod_names: list[str] = []
    for folder in folders:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for descriptor_path, content_root in find_mod_entries(folder):
            mod = load_mod(descriptor_path, content_root)
            if mod is None:
                descriptor = parse_descriptor(descriptor_path)
                empty_mod_names.append(descriptor.get("name", content_root.name).strip() or content_root.name)
                continue
            mods_by_id[mod.mod_id] = mod
    mods = sorted(mods_by_id.values(), key=lambda m: m.name.lower())
    return mods, empty_mod_names


def scan_folders(folders: list[Path]) -> list[Mod]:
    """Scan every supplied folder for HOI4 music mods and return a list of
    Mod objects (deduplicated by resolved content root)."""
    mods, _empty = scan_folders_detailed(folders)
    return mods
