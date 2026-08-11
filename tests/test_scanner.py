import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hoi4_music_player.mod_scanner import scan_folders

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_scan_finds_workshop_style_mod():
    """descriptor.mod inside the mod's own folder (Steam Workshop layout),
    using the simple inline song+file format (no station system) - all its
    tracks should land in a single fallback station named after the mod."""
    stations = scan_folders([FIXTURES_DIR / "Test Music Mod"])
    assert len(stations) == 1, f"expected 1 station, got {len(stations)}"

    station = stations[0]
    assert station.name == "Test Music Mod"
    assert station.mod_name == "Test Music Mod"
    assert station.mod_icon is not None and station.mod_icon.name == "thumbnail.png"
    assert len(station.tracks) == 2

    titles = sorted(t.title for t in station.tracks)
    assert titles == ["Iron and Blood", "March of Nations"]

    for track in station.tracks:
        assert track.file_path.is_file()
        assert track.mod_name == "Test Music Mod"
        assert track.mod_author == "Unknown"

    print("OK: scanner found station:", station.name, "with", len(station.tracks), "tracks")


def test_scan_finds_local_install_style_mod():
    """A standalone <name>.mod sitting next to a sibling content folder,
    like Documents/Paradox Interactive/Hearts of Iron IV/mod/."""
    stations = scan_folders([FIXTURES_DIR / "LocalLayout"])
    assert len(stations) == 1, f"expected 1 station, got {len(stations)}"

    station = stations[0]
    assert station.name == "My Local Mod"
    assert station.mod_icon is not None and station.mod_icon.name == "thumbnail.png"
    assert len(station.tracks) == 1
    assert station.tracks[0].title == "A Locally Installed Song"
    assert station.tracks[0].file_path.is_file()

    print("OK: scanner found local-layout station:", station.name, "with", len(station.tracks), "tracks")


def test_scan_finds_real_asset_and_station_format():
    """The real HOI4 format per the official modding wiki: song definitions
    in *.asset files (name=/file=/volume=), assigned to named stations via
    *.txt files (music_station="key" + music={song="key" chance={...}})."""
    stations = scan_folders([FIXTURES_DIR / "Station Mod"])
    by_name = {s.name: s for s in stations}
    assert set(by_name) == {"Gunka", "Utagoe"}, by_name.keys()

    gunka = by_name["Gunka"]
    assert gunka.mod_name == "Station Mod"
    assert {t.title for t in gunka.tracks} == {"Ageyo Hinomaru", "Battoutai"}
    for track in gunka.tracks:
        assert track.file_path.is_file()
        assert track.station_name == "Gunka"

    utagoe = by_name["Utagoe"]
    assert len(utagoe.tracks) == 1
    assert utagoe.tracks[0].title == "Dai Nippon No Uta"

    print("OK: scanner found real asset+station format:", sorted(by_name))


def test_scan_finds_all_fixture_layouts_together():
    stations = scan_folders([FIXTURES_DIR])
    names = sorted(s.name for s in stations)
    # The Nightcore fixture only ships Russian localisation, so its station
    # names come through in Russian even with the default "en" language -
    # there's nothing English to fall back to for those specific keys.
    assert names == [
        "Gunka", "My Local Mod", "Nightcore Radio 2", "Test Music Mod",
        "Utagoe", 'Радио "Nightcore"',
    ], names
    print("OK: scanning the whole fixtures dir finds every layout (names count):", len(names))


def test_scan_handles_multi_station_file_and_per_track_icons():
    """Modeled on a real published mod: two `music_station = ...` declarations
    in ONE .txt file (one quoted, one not), plus a title localisation that
    embeds a per-track album art reference as `...\\n\\n£GFX_sprite\\n\\n...`
    (see hoi4.paradoxwikis.com's £icon text syntax) resolved via an
    interface/*.gfx spriteType. Both station splitting and per-track icons
    must work for this real-world case, not just the wiki's clean example."""
    stations = scan_folders([FIXTURES_DIR / "Nightcore Mod"], language="ru")
    by_name = {s.name: s for s in stations}
    assert set(by_name) == {'Радио "Nightcore"', "Nightcore Radio 2"}, by_name.keys()

    station1 = by_name['Радио "Nightcore"']
    assert len(station1.tracks) == 1
    track1 = station1.tracks[0]
    # the £ref and its padding \n's must be stripped, not shown as garbage
    assert track1.title == "Nightcore - Dam Dadi Doo", repr(track1.title)
    assert track1.icon is not None and track1.icon.name == "TFR_dam_dadi_doo.png"

    station2 = by_name["Nightcore Radio 2"]
    assert len(station2.tracks) == 1
    track2 = station2.tracks[0]
    assert track2.title == "Nightcore - Roi", repr(track2.title)
    assert track2.icon is not None and track2.icon.name == "TFR_generic.png"

    # each track's per-track icon must differ - this is what "every track
    # in the station shows the same cover" was really about
    assert track1.icon != track2.icon

    print("OK: multi-station file split correctly, and per-track icons differ:",
          track1.icon.name, "vs", track2.icon.name)


if __name__ == "__main__":
    test_scan_finds_workshop_style_mod()
    test_scan_finds_local_install_style_mod()
    test_scan_finds_real_asset_and_station_format()
    test_scan_finds_all_fixture_layouts_together()
    test_scan_handles_multi_station_file_and_per_track_icons()
