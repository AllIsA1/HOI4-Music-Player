"""Cross-platform playback engine built on pygame.mixer (SDL_mixer), which
plays .ogg/.mp3/.wav on both Windows and Linux without extra system deps."""
from __future__ import annotations

import random
from enum import Enum
from typing import Callable, Optional

import pygame

from .models import Track


class RepeatMode(str, Enum):
    OFF = "off"
    ONE = "one"
    ALL = "all"


class PlayerEngine:
    def __init__(self) -> None:
        # pygame.init() (not just mixer.init()) is needed so the SDL event
        # queue used for end-of-track notifications pumps correctly.
        pygame.init()
        pygame.mixer.init()
        self.queue: list[Track] = []
        self.play_order: list[int] = []
        self.position_in_order: int = -1
        self.volume: float = 0.7
        self.shuffle: bool = False
        self.repeat: RepeatMode = RepeatMode.OFF
        self._paused: bool = False
        # pygame.mixer.music.get_pos() returns milliseconds since play() was
        # called and does NOT reset on set_pos() (seeking) - so position has
        # to be tracked as an offset from the last play()/seek() reference
        # point, not read directly from get_pos().
        self._position_base_seconds: float = 0.0
        self._position_base_ticks_ms: int = 0

        self.on_track_change: Optional[Callable[[Optional[Track]], None]] = None
        self.on_playback_state_change: Optional[Callable[[bool], None]] = None

        end_event = pygame.USEREVENT + 1
        self._end_event = end_event
        pygame.mixer.music.set_endevent(end_event)

    # -- queue management -------------------------------------------------
    def set_queue(self, tracks: list[Track], start_track: Optional[Track] = None) -> None:
        self.queue = list(tracks)
        self._rebuild_order(keep_current=False)
        if not self.queue:
            self.position_in_order = -1
            return
        if start_track is not None and start_track in self.queue:
            start_index = self.queue.index(start_track)
            self.position_in_order = self.play_order.index(start_index)
        else:
            self.position_in_order = 0

    def _rebuild_order(self, keep_current: bool) -> None:
        current_index = None
        if keep_current and 0 <= self.position_in_order < len(self.play_order):
            current_index = self.play_order[self.position_in_order]

        indices = list(range(len(self.queue)))
        if self.shuffle:
            random.shuffle(indices)
            if current_index is not None and current_index in indices:
                indices.remove(current_index)
                indices.insert(0, current_index)
        self.play_order = indices

        if current_index is not None and current_index in self.play_order:
            self.position_in_order = self.play_order.index(current_index)
        else:
            self.position_in_order = 0 if self.play_order else -1

    def set_shuffle(self, enabled: bool) -> None:
        self.shuffle = enabled
        self._rebuild_order(keep_current=True)

    def set_repeat(self, mode: RepeatMode) -> None:
        self.repeat = mode

    # -- current track ------------------------------------------------------
    @property
    def current_track(self) -> Optional[Track]:
        if 0 <= self.position_in_order < len(self.play_order):
            return self.queue[self.play_order[self.position_in_order]]
        return None

    def _get_duration(self, track: Track) -> Optional[float]:
        """Returns the cached duration only - never blocks."""
        return track.duration

    # -- transport ----------------------------------------------------------
    def play(self) -> None:
        track = self.current_track
        if track is None:
            return
        pygame.mixer.music.load(str(track.file_path))
        pygame.mixer.music.set_volume(self.volume * track.volume)
        pygame.mixer.music.play()
        self._paused = False
        self._position_base_seconds = 0.0
        self._position_base_ticks_ms = pygame.mixer.music.get_pos()
        if self.on_track_change:
            self.on_track_change(track)
        if self.on_playback_state_change:
            self.on_playback_state_change(True)
        # Duration (if unknown) is intentionally NOT fetched here. Spawning
        # a Python thread to do file I/O (mutagen) while this process also
        # runs SDL_mixer's own audio thread and a Tk mainloop has caused a
        # fatal, unrecoverable interpreter crash (GIL corruption) in
        # practice - it's not worth chasing for a "load a duration" call.
        # The GUI fetches it on the main thread instead (see gui.py).

    def toggle_pause(self) -> None:
        if self.current_track is None:
            return
        if self._paused:
            pygame.mixer.music.unpause()
            self._paused = False
        else:
            pygame.mixer.music.pause()
            self._paused = True
        if self.on_playback_state_change:
            self.on_playback_state_change(not self._paused)

    @property
    def is_playing(self) -> bool:
        return pygame.mixer.music.get_busy() and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._paused

    def stop(self) -> None:
        pygame.mixer.music.stop()
        self._paused = False
        if self.on_playback_state_change:
            self.on_playback_state_change(False)

    def next(self, user_initiated: bool = True) -> None:
        if not self.play_order:
            return
        if self.repeat == RepeatMode.ONE and not user_initiated:
            self.play()
            return
        if self.position_in_order + 1 < len(self.play_order):
            self.position_in_order += 1
        elif self.repeat == RepeatMode.ALL:
            self.position_in_order = 0
            if self.shuffle:
                self._rebuild_order(keep_current=False)
        else:
            self.stop()
            if self.on_track_change:
                self.on_track_change(None)
            return
        self.play()

    def previous(self) -> None:
        if not self.play_order:
            return
        if self.position_in_order > 0:
            self.position_in_order -= 1
        elif self.repeat == RepeatMode.ALL:
            self.position_in_order = len(self.play_order) - 1
        else:
            self.position_in_order = 0
        self.play()

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        track = self.current_track
        track_scale = track.volume if track else 1.0
        pygame.mixer.music.set_volume(self.volume * track_scale)

    def seek(self, seconds: float) -> bool:
        """Jump to a position in the current track. Returns False if the
        format doesn't support seeking (pygame/SDL_mixer only supports
        set_pos() for OGG and MP3 - not WAV) rather than raising."""
        track = self.current_track
        if track is None:
            return False
        seconds = max(0.0, seconds)
        was_paused = self._paused
        try:
            pygame.mixer.music.set_pos(seconds)
        except pygame.error:
            return False
        if was_paused:
            # set_pos() on some backends resumes playback - restore pause.
            pygame.mixer.music.pause()
        self._position_base_seconds = seconds
        self._position_base_ticks_ms = pygame.mixer.music.get_pos()
        return True

    def get_position_seconds(self) -> float:
        if self.current_track is None:
            return 0.0
        pos_ms = pygame.mixer.music.get_pos()
        if pos_ms < 0:
            return self._position_base_seconds
        elapsed = (pos_ms - self._position_base_ticks_ms) / 1000.0
        return max(0.0, self._position_base_seconds + elapsed)

    def get_duration_seconds(self) -> Optional[float]:
        track = self.current_track
        if track is None:
            return None
        return self._get_duration(track)

    def poll_events(self) -> None:
        """Call periodically (e.g. from a GUI timer) to advance the queue
        when the current track finishes naturally."""
        for event in pygame.event.get():
            if event.type == self._end_event and not self._paused:
                self.next(user_initiated=False)
