"""
Scans user-supplied folders for Hearts of Iron IV mods and extracts music
track metadata straight from the real mod file structure:

    <mod_root>/descriptor.mod          -> mod name / author / thumbnail
    <mod_root>/music/**/*.txt          -> music = { song = "..." file = "..." volume = ... }
    <mod_root>/localisation/**/*.yml   -> localisation of song keys -> display titles

No extra/custom config files are required or read. This mirrors the format
Paradox and mod authors actually ship music mods in.
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


def find_mod_roots(base_dir: Path) -> list[Path]:
    """Find every mod root under base_dir. A mod root is any directory that
    directly contains a descriptor.mod file. base_dir itself is checked first
    (flat mod folder), then subdirectories are searched recursively up to a
    depth limit (covers Steam Workshop layouts like content/<appid>/<id>/)."""
    base_dir = Path(base_dir)
    roots: list[Path] = []

    if (base_dir / "descriptor.mod").is_file():
        roots.append(base_dir)
        return roots

    def _walk(directory: Path, depth: int):
        if depth > MAX_DESCRIPTOR_SEARCH_DEPTH:
            return
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if not entry.is_dir():
                continue
            if (entry / "descriptor.mod").is_file():
                roots.append(entry)
            else:
                _walk(entry, depth + 1)

    _walk(base_dir, 0)
    return roots


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


def load_mod(mod_root: Path) -> Optional[Mod]:
    descriptor_path = mod_root / "descriptor.mod"
    if not descriptor_path.is_file():
        return None

    descriptor = parse_descriptor(descriptor_path)
    name = descriptor.get("name", mod_root.name).strip() or mod_root.name
    author = _guess_author(descriptor, mod_root)

    icon: Optional[Path] = None
    picture_name = descriptor.get("picture")
    if picture_name:
        candidate = mod_root / picture_name
        if candidate.is_file():
            icon = candidate
    if icon is None:
        for fallback in ("thumbnail.png", "thumbnail.jpg"):
            candidate = mod_root / fallback
            if candidate.is_file():
                icon = candidate
                break

    localisation = parse_localisation(mod_root)
    raw_tracks = parse_music_tracks(mod_root)
    if not raw_tracks:
        return None

    mod_id = str(mod_root.resolve())
    mod = Mod(mod_id=mod_id, name=name, author=author, root=mod_root, icon=icon)

    seen_files: set[str] = set()
    for raw in raw_tracks:
        resolved = _resolve_audio_path(mod_root, raw["file"])
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


def scan_folders(folders: list[Path]) -> list[Mod]:
    """Scan every supplied folder for HOI4 music mods and return a list of
    Mod objects (deduplicated by resolved mod root)."""
    mods_by_id: dict[str, Mod] = {}
    for folder in folders:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for mod_root in find_mod_roots(folder):
            mod = load_mod(mod_root)
            if mod is None:
                continue
            mods_by_id[mod.mod_id] = mod
    return sorted(mods_by_id.values(), key=lambda m: m.name.lower())
