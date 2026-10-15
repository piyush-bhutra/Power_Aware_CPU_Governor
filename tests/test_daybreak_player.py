"""Finite shared playback, using a deterministic clock instead of sleeps."""
import importlib


def player(total=34):
    return importlib.import_module('daybreak.player').Player('synthetic', total)


def test_pause_resume_completion_and_restart():
    p = player(5)
    p.play(0)
    assert p.advance(.9) == 1
    assert p.advance(1) == 2
    p.pause()
    assert p.advance(99) == 2
    p.play(100)
    assert p.advance(101) == 3
    assert p.advance(102) == 4
    assert p.advance(103) == 5
    assert p.complete and not p.playing
    p.restart(104)
    assert p.tick == 1 and p.playing


def test_seek_manual_speed_and_switch_use_actual_count():
    p = player()
    p.play(0)
    p.seek(11)
    assert not p.playing and p.tick == 11
    p.step(-1)
    assert p.tick == 10
    p.set_speed(2, 10)
    p.play(10)
    assert p.advance(10.5) == 11
    p.switch('saved', 5, 20)
    assert p.source == 'saved' and p.total == 5 and p.tick == 1
    p.seek(99)
    assert p.tick == 5
    p.step(-1)
    assert p.tick == 4


def test_delayed_rerun_never_skips_samples():
    p = player(5)
    p.play(0)
    assert p.advance(100) == 2
    assert p.advance(100) == 2
