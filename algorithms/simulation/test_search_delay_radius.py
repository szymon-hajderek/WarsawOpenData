"""Run from backend/: uv run pytest ../algorithms"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from search_delay_radius import best_neighbours, best_radius  # noqa: E402
from simulate_delay import _shown  # noqa: E402


def row(r, s):
    return {"radius_m": r, "score": s}


def test_best_neighbours_picks_highest_pair():
    coarse = [row(r, s) for r, s in [(20, .5), (30, .7), (40, .8), (50, .75), (60, .6)]]
    assert best_neighbours(coarse) == (40, 50)


def test_best_neighbours_tie_takes_smaller():
    assert best_neighbours([row(20, .5), row(30, .5), row(40, .5)]) == (20, 30)


def test_best_radius_tie_takes_smaller():
    assert best_radius([row(40, .8), row(41, .9), row(42, .9)])["radius_m"] == 41


def test_shown_is_first_observation_within_radius():
    obs = [(45.0, 10), (28.0, 12), (12.0, 15)]
    assert _shown(obs, 30) == 12 and _shown(obs, 50) == 10 and _shown(obs, 10) is None
