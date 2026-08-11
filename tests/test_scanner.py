import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hoi4_music_player.mod_scanner import scan_folders

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_scan_finds_workshop_style_mod():
    """descriptor.mod inside the mod's own folder (Steam Workshop layout)."""
    mods = scan_folders([FIXTURES_DIR / "Test Music Mod"])
    assert len(mods) == 1, f"expected 1 mod, got {len(mods)}"

    mod = mods[0]
    assert mod.name == "Test Music Mod"
    assert mod.icon is not None and mod.icon.name == "thumbnail.png"
    assert len(mod.tracks) == 2

    titles = sorted(t.title for t in mod.tracks)
    assert titles == ["Iron and Blood", "March of Nations"]

    for track in mod.tracks:
        assert track.file_path.is_file()
        assert track.mod_name == "Test Music Mod"
        assert track.mod_author == "Unknown"

    print("OK: scanner found mod:", mod.name, "with", len(mod.tracks), "tracks")


def test_scan_finds_local_install_style_mod():
    """A standalone <name>.mod sitting next to a sibling content folder,
    like Documents/Paradox Interactive/Hearts of Iron IV/mod/ - this is how
    manually-installed (non-Workshop) mods are laid out on disk."""
    mods = scan_folders([FIXTURES_DIR / "LocalLayout"])
    assert len(mods) == 1, f"expected 1 mod, got {len(mods)}"

    mod = mods[0]
    assert mod.name == "My Local Mod"
    assert mod.icon is not None and mod.icon.name == "thumbnail.png"
    assert len(mod.tracks) == 1
    assert mod.tracks[0].title == "A Locally Installed Song"
    assert mod.tracks[0].file_path.is_file()

    print("OK: scanner found local-layout mod:", mod.name, "with", len(mod.tracks), "tracks")


def test_scan_finds_both_layouts_together():
    mods = scan_folders([FIXTURES_DIR])
    names = sorted(m.name for m in mods)
    assert names == ["My Local Mod", "Test Music Mod"], names
    print("OK: scanning the whole fixtures dir finds both layouts:", names)


if __name__ == "__main__":
    test_scan_finds_workshop_style_mod()
    test_scan_finds_local_install_style_mod()
    test_scan_finds_both_layouts_together()
