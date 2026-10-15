"""Finite presentation clock shared by all verified session sources."""
from dataclasses import dataclass
import math


@dataclass
class Player:
    source: str
    total: int
    tick: int = 1
    speed: float = 1.0
    playing: bool = False
    due: float = math.inf

    def __post_init__(self):
        if self.total < 1:
            raise ValueError('Session has no samples')

    @property
    def complete(self):
        return self.tick == self.total

    def play(self, now):
        self.playing = not self.complete
        self.due = now + 1 / self.speed

    def pause(self):
        self.playing = False
        self.due = math.inf

    def advance(self, now):
        # Never skip observations if rendering/browser scheduling is slow.
        if self.playing and now >= self.due:
            self.tick = min(self.total, self.tick + 1)
            self.due = now + 1 / self.speed
            if self.complete:
                self.pause()
        return self.tick

    def seek(self, tick):
        self.pause()
        self.tick = max(1, min(self.total, int(tick)))

    def step(self, delta):
        self.seek(self.tick + delta)

    def restart(self, now):
        self.tick = 1
        self.play(now)

    def set_speed(self, speed, now):
        if speed not in (.5, 1.0, 2.0, 4.0):
            raise ValueError('Unsupported playback speed')
        self.speed = speed
        self.due = now + 1 / speed if self.playing else math.inf

    def switch(self, source, total, now):
        if total < 1:
            raise ValueError('Session has no samples')
        self.source, self.total = source, total
        self.restart(now)
