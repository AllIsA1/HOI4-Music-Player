"""Persistent user settings: added folders, volume, playback mode, enabled mods."""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".hoi4_music_player"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULTS = {
    "folders": [],
    "disabled_mod_ids": [],
    "volume": 0.7,
}


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.data = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        if self.path.is_file():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                self.data.update({k: loaded.get(k, v) for k, v in DEFAULTS.items()})
            except (OSError, json.JSONDecodeError):
                pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.write_text(
                json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass

    @property
    def folders(self) -> list[str]:
        return self.data["folders"]

    def add_folder(self, folder: str) -> bool:
        folder = str(Path(folder))
        if folder in self.data["folders"]:
            return False
        self.data["folders"].append(folder)
        self.save()
        return True

    def remove_folder(self, folder: str) -> bool:
        folder = str(Path(folder))
        if folder not in self.data["folders"]:
            return False
        self.data["folders"].remove(folder)
        self.save()
        return True

    @property
    def disabled_mod_ids(self) -> set[str]:
        return set(self.data["disabled_mod_ids"])

    def set_mod_enabled(self, mod_id: str, enabled: bool) -> None:
        disabled = set(self.data["disabled_mod_ids"])
        if enabled:
            disabled.discard(mod_id)
        else:
            disabled.add(mod_id)
        self.data["disabled_mod_ids"] = sorted(disabled)
        self.save()

    @property
    def volume(self) -> float:
        return float(self.data["volume"])

    @volume.setter
    def volume(self, value: float) -> None:
        self.data["volume"] = max(0.0, min(1.0, value))
        self.save()
