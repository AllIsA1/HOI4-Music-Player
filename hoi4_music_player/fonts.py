"""Registers the bundled fonts (renamed IBM Plex, see fonts/README.txt) for
this process only - nothing is installed system-wide - with a fallback to
stock system fonts."""
from __future__ import annotations

import ctypes
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "fonts"

BUNDLED = {
    "sans": "HMP Sans",
    "sans_medium": "HMP Sans Medium",
    "sans_semibold": "HMP Sans SemiBold",
    "mono": "HMP Mono",
}


def _register_files() -> None:
    files = sorted(FONT_DIR.glob("*.ttf"))
    if sys.platform == "win32":
        FR_PRIVATE = 0x10
        add = ctypes.windll.gdi32.AddFontResourceExW
        for path in files:
            add(str(path), FR_PRIVATE, 0)
    else:
        # Loading by soname returns the libfontconfig that Tk's Xft backend
        # already has mapped, so the fonts land in the config Tk queries.
        fc = ctypes.CDLL("libfontconfig.so.1")
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        fc.FcConfigAppFontAddFile.restype = ctypes.c_int
        for path in files:
            fc.FcConfigAppFontAddFile(None, str(path).encode())


def _resolves(root: tk.Misc, family: str) -> bool:
    return tkfont.Font(root, family=family, size=12).actual("family").lower() == family.lower()


def register_bundled_fonts(root: tk.Misc) -> dict[str, str]:
    """Returns the family names to use for each role - the bundled families
    when registration worked, stock system fonts otherwise."""
    try:
        _register_files()
    except Exception:
        pass
    if _resolves(root, BUNDLED["sans"]) and _resolves(root, BUNDLED["mono"]):
        families = dict(BUNDLED)
        for role in ("sans_medium", "sans_semibold"):
            if not _resolves(root, families[role]):
                families[role] = BUNDLED["sans"]
        return families

    if sys.platform == "win32":
        sans, mono = "Segoe UI", "Consolas"
    else:
        available = set(tkfont.families(root))
        sans = next((f for f in ("Noto Sans", "DejaVu Sans", "Liberation Sans") if f in available), "TkDefaultFont")
        mono = next((f for f in ("Noto Sans Mono", "DejaVu Sans Mono", "Liberation Mono") if f in available), "TkFixedFont")
    return {"sans": sans, "sans_medium": sans, "sans_semibold": sans, "mono": mono}
