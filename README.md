# HOI4 Music Player

A standalone desktop music player for **Hearts of Iron IV** music mods. Point it at
the folder(s) where your HOI4 mods live, and it reads each mod's own files to
build a browsable, filterable playlist grouped by **radio station** — track
title, which station and mod it came from, the mod's icon, volume, search, and
normal playback controls.

Works on **Windows** and **Linux** (tested on Ubuntu/Debian).

> **Read-only.** The player never writes to, modifies, or deletes anything inside
> your mod folders. It only reads `descriptor.mod`/`<name>.mod`, the `music/` and
> `localisation/` files, and streams the audio. The only file it ever writes is
> its own settings file in your home directory (see [Configuration](#configuration)).

## How it detects mods

No extra config files or setup are needed — it reads the real HOI4 mod structure
that mod authors already ship, per the [official modding wiki](https://hoi4.paradoxwikis.com/Music_modding):

| File | Used for |
|---|---|
| `descriptor.mod` (or a standalone `<name>.mod`) | Mod name, and its `picture=` thumbnail as the mod's icon |
| `music/**/*.asset` | Song definitions: `music = { name = "KEY" file = "x.ogg" volume = 0.65 }` |
| `music/**/*.txt` | Station assignments: `music_station = "key"` + `music = { song = "KEY" chance = {...} }` |
| `localisation/**/*.yml` | Song titles (by `KEY`) and station display names (by `key_TITLE`) |

Each **station** (radio channel, e.g. "Gunka", "Peacetime") becomes its own entry in
the sidebar, showing every song assigned to it. Mods that don't use the station
system at all (older/simpler mods that just put `song =`/`file =` together in one
block) still work — their tracks land under a single fallback "station" named
after the mod.

Add a folder (the **Folders** button, or **Add folder…** on first launch) that either:
- **is** a single mod (contains a `descriptor.mod`/`<name>.mod` directly), or
- **contains** several mods — e.g. a Steam Workshop `content/<appid>/` folder, or
  your `Documents/Paradox Interactive/Hearts of Iron IV/mod/` folder — every mod
  inside is picked up automatically (recursive, a few levels deep). Both real HOI4
  install layouts are supported: Steam Workshop (`descriptor.mod` inside the mod's
  own folder) and local/manual installs (a standalone `<name>.mod` sitting next to
  its content folder).

A mod with no music tracks is skipped. HOI4 has no separate artist field, but most
mods name their tracks "Artist - Title" — the player splits that (a hyphen, en dash
or em dash all work) into the Artist and Title columns; a name without that
separator shows its artist as "Unknown".

## Features

- Browse tracks by radio station, or across "All stations" at once; double-click a station to play it
- Switch individual stations on/off with the lamp next to them — a switched-off station's tracks never show up or play
- Search by track title, artist, station or mod
- Play / pause / previous / next, shuffle, repeat (all / one), volume and mute
- Seek on the tuning dial — click or drag anywhere on it
- Shows each track's real duration (read in the background after scanning)
- Per-track album art in the list (when a mod has it), mod art in the player bar
- Keyboard: <kbd>Space</kbd> play/pause, <kbd>Ctrl</kbd>+<kbd>F</kbd> search, <kbd>Esc</kbd> clear search, <kbd>Enter</kbd> play the selected track
- English/Russian UI, and prefers a mod's Russian localisation for track/station names when available (falls back to English per-key if a translation is missing)

## Download

Grab the latest build from the [Releases page](../../releases) — no installation needed:

- **Windows:** `HOI4MusicPlayer.exe`
- **Linux:** `HOI4MusicPlayer-x86_64.AppImage` — `chmod +x` it and run

## Running from source

Requires **Python 3.10+**.

```bash
git clone https://github.com/AllIsA1/HOI4-Music-Player.git
cd HOI4-Music-Player
python -m venv .venv
```

**Windows:**
```bash
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install python3-venv python3-tk
source .venv/bin/activate
pip install -r requirements.txt
python3 run.py
```
`python3-tk` is required (Tkinter isn't bundled with Python on Debian/Ubuntu). Everything
else (audio playback, image handling, the UI toolkit) comes from `requirements.txt`.

## Building a standalone binary

**Windows** — produces `dist\HOI4MusicPlayer.exe`:
```bash
packaging\build_windows.bat
```

**Linux** — produces `dist/HOI4MusicPlayer`:
```bash
sudo apt install python3-venv python3-tk
chmod +x packaging/build_linux.sh
./packaging/build_linux.sh
```

Both scripts create/reuse a `.venv`, install dependencies, install PyInstaller, and
build a one-file, windowed binary with the app icon embedded.

## Configuration

Settings (added folders, volume, language, shuffle/repeat, which stations are switched off) are stored at:

- Windows: `%USERPROFILE%\.hoi4_music_player\config.json`
- Linux: `~/.hoi4_music_player/config.json`

Delete that file to reset the player to a clean state.

## Tech stack

- Tk/ttk (Python's standard `tkinter`) for the UI, with bundled [IBM Plex](https://github.com/IBM/plex) fonts (SIL OFL 1.1, see `hoi4_music_player/fonts/`)
- [pygame](https://www.pygame.org/) (`pygame.mixer`) for cross-platform `.ogg`/`.mp3`/`.wav` playback
- [mutagen](https://mutagen.readthedocs.io/) to read track durations
- [Pillow](https://python-pillow.org/) for icons

## License

[MIT](LICENSE)
