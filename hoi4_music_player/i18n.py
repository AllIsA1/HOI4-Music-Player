"""Minimal i18n for the player's own UI chrome (English/Russian)."""
from __future__ import annotations

DEFAULT_LANGUAGE = "en"
LANGUAGES = ("en", "ru")

# HOI4's localisation folder/tag naming per language, used to pick which of
# a mod's own localisation files to prefer (see mod_scanner.parse_localisation).
HOI4_LANGUAGE_TAG = {"en": "l_english", "ru": "l_russian"}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "HOI4 Music Player",
        "manage_folders": "  Manage Folders…",
        "stations": "STATIONS",
        "all_stations": "All Stations",
        "search_placeholder": "Search tracks, stations, mods…",
        "tracks_header": "Tracks ({count})",
        "play_all": "  Play All",
        "nothing_playing": "Nothing playing",
        "add_folder_hint": "Add a mod folder to get started",
        "no_folders": "No folders added — click 'Manage Folders…'",
        "scanning": "Scanning…",
        "no_mod_found": "No .mod/descriptor.mod found in the added folders",
        "found_empty_mods": "Found mod(s) ({names}) but no tracks in their music/ folder",
        "stations_summary": "{count} stations, {tracks} tracks",
        "more_empty_mods": " ({count} more found with no music/ tracks)",
        "no_tracks_message": "No tracks to show. Add folders with HOI4 music mods, "
                              "or adjust your search/filters.",
        "manage_folders_title": "Manage Mod Folders",
        "manage_folders_body": "Add the folders where your HOI4 music mods live\n"
                                "(a Steam Workshop content folder, or your own mods directory).",
        "add_folder_btn": "  Add Folder…",
        "close": "Close",
        "no_folders_yet": "No folders added yet.",
        "remove": "Remove",
        "col_track": "Track",
        "col_station": "Station",
        "col_mod": "Mod",
        "col_author": "Author",
        "col_time": "Time",
        "unknown_author": "Unknown",
        "select_folder_dialog": "Select a folder containing HOI4 mods",
        "station_subtitle": "{mod} • {count} tracks",
    },
    "ru": {
        "app_title": "HOI4 Музыкальный плеер",
        "manage_folders": "  Папки с модами…",
        "stations": "СТАНЦИИ",
        "all_stations": "Все станции",
        "search_placeholder": "Поиск по трекам, станциям, модам…",
        "tracks_header": "Треки ({count})",
        "play_all": "  Играть всё",
        "nothing_playing": "Ничего не играет",
        "add_folder_hint": "Добавьте папку с модом, чтобы начать",
        "no_folders": "Папки не добавлены — нажмите «Папки с модами…»",
        "scanning": "Сканирование…",
        "no_mod_found": "В добавленных папках не найден .mod/descriptor.mod",
        "found_empty_mods": "Найдены моды ({names}), но в их папке music/ нет треков",
        "stations_summary": "Станций: {count}, треков: {tracks}",
        "more_empty_mods": " (ещё {count} без треков в music/)",
        "no_tracks_message": "Нет треков для отображения. Добавьте папки с музыкальными "
                              "модами HOI4 или измените поиск/фильтры.",
        "manage_folders_title": "Папки с модами",
        "manage_folders_body": "Добавьте папки, где лежат ваши музыкальные моды HOI4\n"
                                "(папка Steam Workshop или ваша собственная папка модов).",
        "add_folder_btn": "  Добавить папку…",
        "close": "Закрыть",
        "no_folders_yet": "Папки ещё не добавлены.",
        "remove": "Удалить",
        "col_track": "Трек",
        "col_station": "Станция",
        "col_mod": "Мод",
        "col_author": "Автор",
        "col_time": "Время",
        "unknown_author": "Неизвестен",
        "select_folder_dialog": "Выберите папку с модами HOI4",
        "station_subtitle": "{mod} • {count} треков",
    },
}


def t(language: str, key: str, **kwargs) -> str:
    table = STRINGS.get(language, STRINGS[DEFAULT_LANGUAGE])
    text = table.get(key, STRINGS[DEFAULT_LANGUAGE].get(key, key))
    return text.format(**kwargs) if kwargs else text
