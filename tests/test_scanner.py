import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hoi4_music_player.mod_scanner import scan_folders

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_scan_finds_mod_and_tracks():
    mods = scan_folders([FIXTURES_DIR])
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


if __name__ == "__main__":
    test_scan_finds_mod_and_tracks()
