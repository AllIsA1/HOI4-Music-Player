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
        "stations": "Stations",
        "all_stations": "All stations",
        "search_placeholder": "Search tracks, artists, stations",
        "play": "Play",
        "folders": "Folders",
        "nothing_playing": "Nothing playing",
        "pick_track_hint": "Double-click a track to start",
        "scanning": "Scanning mod folders…",
        "col_title": "Title",
        "col_author": "Artist",
        "col_station": "Station",
        "col_mod": "Mod",
        "col_time": "Time",
        "unknown_author": "Unknown",
        "empty_start_title": "No music yet",
        "empty_start_body": "Add the folder your HOI4 mods live in — the Steam Workshop "
                            "folder (…/workshop/content/394360) or your own mod directory.",
        "add_folder": "Add folder…",
        "empty_search_title": "Nothing found",
        "empty_search_body": "No tracks match “{query}”.",
        "clear_search": "Clear search",
        "empty_off_title": "This station is off",
        "empty_off_body": "Its tracks are hidden and never play while it's switched off.",
        "turn_on": "Turn on",
        "empty_none_title": "No tracks found",
        "no_mod_found": "No .mod or descriptor.mod files were found in the added folders.",
        "found_empty_mods": "Found {names}, but none of them have tracks in a music/ folder.",
        "manage_folders": "Manage folders…",
        "folders_title": "Mod folders",
        "folders_body": "Every folder here is scanned for HOI4 mods with music.",
        "no_folders_yet": "No folders added yet.",
        "remove": "Remove",
        "done": "Done",
        "select_folder_dialog": "Select a folder containing HOI4 mods",
        "shuffle": "Shuffle",
        "repeat": "Repeat",
        "rescan": "Rescan folders",
    },
    "ru": {
        "app_title": "HOI4 Музыкальный плеер",
        "stations": "Станции",
        "all_stations": "Все станции",
        "search_placeholder": "Поиск: трек, автор, станция",
        "play": "Слушать",
        "folders": "Папки",
        "nothing_playing": "Ничего не играет",
        "pick_track_hint": "Дважды щёлкните по треку",
        "scanning": "Сканирование папок с модами…",
        "col_title": "Название",
        "col_author": "Автор",
        "col_station": "Станция",
        "col_mod": "Мод",
        "col_time": "Время",
        "unknown_author": "Неизвестен",
        "empty_start_title": "Музыки пока нет",
        "empty_start_body": "Добавьте папку с модами HOI4 — папку Steam Workshop "
                            "(…/workshop/content/394360) или свою папку модов.",
        "add_folder": "Добавить папку…",
        "empty_search_title": "Ничего не найдено",
        "empty_search_body": "Нет треков по запросу «{query}».",
        "clear_search": "Сбросить поиск",
        "empty_off_title": "Станция выключена",
        "empty_off_body": "Пока она выключена, её треки скрыты и не играют.",
        "turn_on": "Включить",
        "empty_none_title": "Треки не найдены",
        "no_mod_found": "В добавленных папках нет файлов .mod или descriptor.mod.",
        "found_empty_mods": "Найдены моды: {names}, но ни в одном нет треков в папке music/.",
        "manage_folders": "Управление папками…",
        "folders_title": "Папки с модами",
        "folders_body": "В каждой папке из списка ищутся моды HOI4 с музыкой.",
        "no_folders_yet": "Папки ещё не добавлены.",
        "remove": "Убрать",
        "done": "Готово",
        "select_folder_dialog": "Выберите папку с модами HOI4",
        "shuffle": "Перемешать",
        "repeat": "Повтор",
        "rescan": "Пересканировать папки",
    },
}

_NOUNS: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {
        "track": ("track", "tracks"),
        "station": ("station", "stations"),
        "mod_without_music": ("mod without music", "mods without music"),
    },
    "ru": {
        "track": ("трек", "трека", "треков"),
        "station": ("станция", "станции", "станций"),
        "mod_without_music": ("мод без музыки", "мода без музыки", "модов без музыки"),
    },
}


def t(language: str, key: str, **kwargs) -> str:
    table = STRINGS.get(language, STRINGS[DEFAULT_LANGUAGE])
    text = table.get(key, STRINGS[DEFAULT_LANGUAGE].get(key, key))
    return text.format(**kwargs) if kwargs else text


def number(language: str, value: int) -> str:
    grouped = f"{value:,}"
    return grouped.replace(",", " ") if language == "ru" else grouped


def count(language: str, value: int, noun: str) -> str:
    """'1 track' / '5 tracks', '1 трек' / '3 трека' / '5 треков'."""
    forms = _NOUNS.get(language, _NOUNS[DEFAULT_LANGUAGE])[noun]
    if language == "ru":
        tail, tail100 = value % 10, value % 100
        if tail == 1 and tail100 != 11:
            word = forms[0]
        elif 2 <= tail <= 4 and not 12 <= tail100 <= 14:
            word = forms[1]
        else:
            word = forms[2]
    else:
        word = forms[0] if value == 1 else forms[1]
    return f"{number(language, value)} {word}"
