"""Route engine checks on several trips: there are options, and none leaves long after the query.
A trip with `needs_transit` must also get a public transport option.

A trip with `known_bug` in the scenario is a bug these tests found in the engine. It runs as a strict
xfail: when the engine is fixed the test reports XPASS and fails, so remove `known_bug` then.
"""
import json
from datetime import datetime

import pytest

import results
from planning import plan
from sim import api as sim_api
from sim import clock, scenario as sim_scenario

pytestmark = pytest.mark.gtfs

SPEC = json.loads(sim_scenario.find("engine-sanity").read_text(encoding="utf-8"))
_rows: dict[str, dict] = {}


def _case(trip):
    marks = [pytest.mark.xfail(strict=True, reason=trip["known_bug"])] if trip.get("known_bug") else []
    return pytest.param(trip, id=trip["name"], marks=marks)


@pytest.mark.parametrize("trip", [_case(t) for t in SPEC["test"]["trips"]])
def test_options_leave_soon(client, gtfs_ready, osm_ready, scenario, trip):
    scenario("engine-sanity")
    asked = clock.warsaw_epoch(datetime.fromisoformat(trip["at"]))
    sim_api.step(to=asked)
    options = plan(client, {"from": {"id": "a", "label": "A", "position": trip["from"]},
                            "to": {"id": "b", "label": "B", "position": trip["to"]}})
    limit = SPEC["test"]["max_wait_min"]
    asked_min = clock.warsaw_time(asked).hour * 60 + clock.warsaw_time(asked).minute
    waits = {}
    for o in options:
        h, m = map(int, o["departure"].split(":"))
        waits[f"{o['title']} {o['departure']}"] = (h * 60 + m - asked_min) % 1440
    late = [k for k, w in waits.items() if w > limit]
    transit = [o for o in options if {leg["mode"] for leg in o["legs"]} & {"bus", "tram", "metro", "rail"}]
    checks = [("at least one option", bool(options)), (f"every option leaves within {limit} min", not late)]
    if trip.get("needs_transit"):
        checks.append(("at least one public transport option", bool(transit)))
    _rows[trip["name"]] = {"at": trip["at"][11:16], "options": len(options), "late options": ", ".join(late) or "-",
                           "known bug": trip.get("known_bug", "-"), "ok": all(ok for _, ok in checks)}
    results.record("engine-sanity", SPEC["title"], "gtfs",
                   {name: f"{r['options']} options at {r['at']}; late: {r['late options']}" for name, r in _rows.items()},
                   [(f"{name}: options exist and leave soon"
                     + (f" (known bug: {r['known bug']})" if r["known bug"] != "-" else ""), r["ok"])
                    for name, r in _rows.items()])
    for name, ok in checks:
        assert ok, name
