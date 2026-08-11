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

Point "Manage Folders…" at a folder that either:
- **is** a single mod (contains a `descriptor.mod`/`<name>.mod` directly), or
- **contains** several mods — e.g. a Steam Workshop `content/<appid>/` folder, or
  your `Documents/Paradox Interactive/Hearts of Iron IV/mod/` folder — every mod
  inside is picked up automatically (recursive, a few levels deep). Both real HOI4
  install layouts are supported: Steam Workshop (`descriptor.mod` inside the mod's
  own folder) and local/manual installs (a standalone `<name>.mod` sitting next to
  its content folder).

A mod with no music tracks is skipped. The author field isn't part of the
standard HOI4 mod format, so it's used when a mod happens to provide one
(non-standard `author=` field in `descriptor.mod`, or an `author.txt`/`credits.txt`
file); otherwise it shows as "Unknown".

## Features

- Browse tracks by radio station, or across "All Stations" at once
- Enable/disable individual stations — disabled stations' tracks never show up or play
- Search by track title, station name, mod name, or author
- Play / pause / previous / next, volume control
- Shows each track's real duration (read in the background after scanning)
- Mod icon shown per track and in the now-playing bar

## Download

Grab the latest Windows build from the [Releases page](../../releases) — a single
`HOI4MusicPlayer.exe`, no installation needed. On Linux, build the binary yourself
(one command, see below) or run it directly from source.

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

Settings (added folders, volume, which stations are disabled) are stored at:

- Windows: `%USERPROFILE%\.hoi4_music_player\config.json`
- Linux: `~/.hoi4_music_player/config.json`

Delete that file to reset the player to a clean state.

## Tech stack

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for the UI
- [pygame](https://www.pygame.org/) (`pygame.mixer`) for cross-platform `.ogg`/`.mp3`/`.wav` playback
- [mutagen](https://mutagen.readthedocs.io/) to read track durations
- [Pillow](https://python-pillow.org/) for icons

## License

[MIT](LICENSE)
