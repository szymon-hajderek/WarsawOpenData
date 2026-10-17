"""Find the best radius R for the delay estimate on a recording (two-step grid search).

Run from backend/:  uv run python ../algorithms/simulation/search_delay_radius.py [--sample ...] [--from 20] [--to 200]

1. Coarse: R = 20, 30, ..., 200 m (step 10).
2. Take the two neighbouring coarse radii (10 m apart) with the best scores together, e.g. 40 and 50 m.
3. Fine: every 1 m between them (40, 41, ..., 50); the best one wins (ties: the smaller radius).
Score = share of all passes for which the user sees a delay within 30 s of the reference (simulate_delay._metrics):
a radius that is too small loses availability, one that is too large loses accuracy.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate_delay as sd  # noqa: E402


def best_neighbours(coarse: list[dict]) -> tuple[float, float]:
    """The two neighbouring radii with the highest summed score (ties: the smaller radii)."""
    i = max(range(len(coarse) - 1), key=lambda k: (coarse[k]["score"] + coarse[k + 1]["score"], -k))
    return coarse[i]["radius_m"], coarse[i + 1]["radius_m"]


def best_radius(fine: list[dict]) -> dict:
    """The radius with the highest score (ties: the smaller radius)."""
    return max(fine, key=lambda m: (m["score"], -m["radius_m"]))


def search(sample: dict, lo: int = 20, hi: int = 200, coarse_step: int = 10, fine_step: int = 1, **kw) -> dict:
    coarse = sd.evaluate_many(sample, list(range(lo, hi + 1, coarse_step)), **kw)
    a, b = best_neighbours(coarse)
    fine = sd.evaluate_many(sample, list(range(int(a), int(b) + 1, fine_step)), **kw)
    return {"coarse": coarse, "pair": [a, b], "fine": fine, "best": best_radius(fine)}


def _row(m: dict) -> str:
    return (f"| {m['radius_m']:g} | {100 * m['score']:.1f}% | {100 * m['available']:.1f}% "
            f"| {m['abs_err_median']} | {m['abs_err_p90']} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=Path, default=sd.SAMPLE)
    ap.add_argument("--from", dest="lo", type=int, default=20)
    ap.add_argument("--to", dest="hi", type=int, default=200)
    a = ap.parse_args()
    res = search(sd.load(a.sample), a.lo, a.hi)
    head = "| R (m) | score | available | median abs error (s) | p90 abs error (s) |\n|---|---|---|---|---|"
    print(head)
    print("\n".join(_row(m) for m in res["coarse"]))
    print(f"\nbest neighbours: {res['pair'][0]:g} and {res['pair'][1]:g} m, every 1 m:\n")
    print(head)
    print("\n".join(_row(m) for m in res["fine"]))
    print(f"\nbest R = {res['best']['radius_m']:g} m, score {100 * res['best']['score']:.1f}%")
    print(json.dumps({"best_radius_m": res["best"]["radius_m"]}))


if __name__ == "__main__":
    main()
