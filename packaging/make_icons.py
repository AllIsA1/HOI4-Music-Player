"""Regenerates assets/icon.png and assets/icon.ico from hoi4_music_player/brand.py.
Run from the repo root after changing the icon: python packaging/make_icons.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hoi4_music_player.brand import app_icon  # noqa: E402
from hoi4_music_player.utils import write_ico  # noqa: E402

app_icon(256).save(ROOT / "assets" / "icon.png")
write_ico(ROOT / "assets" / "icon.ico")
print("Wrote assets/icon.png and assets/icon.ico")
