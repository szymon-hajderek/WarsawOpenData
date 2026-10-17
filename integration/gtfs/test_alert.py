"""Scenario 5: a ZTM alert for the planned line starts 2 min after the query. From then on every option
with that line carries the tag "Zmiana na trasie", and the others do not."""
import pytest

import results
from planning import lines, plan, surface_transit
from sim import api as sim_api

pytestmark = pytest.mark.gtfs

TAG = "Zmiana na trasie"


def test_alert_tags_the_line(client, gtfs_ready, osm_ready, scenario):
    sc = scenario("alert-wilenski-waszyngtona")
    trip, after_s = sc.spec["trip"], sc.spec["test"]["alert_after_s"]
    first = surface_transit(plan(client, trip))
    assert first, "no bus / tram option"
    line = next(leg["line"] for leg in first["legs"] if leg["mode"] in ("bus", "tram"))
    sc.add_alert([line], at=sc.start + after_s)

    early = plan(client, trip)
    sim_api.step(after_s)
    late = plan(client, trip)
    with_line = [o for o in late if line in lines(o)]
    without = [o for o in late if line not in lines(o)]

    checks = [
        ("no tag before the alert starts", not any(TAG in o["tags"] for o in early)),
        ("an option still uses the line after the alert", bool(with_line)),
        ("every option with the line has the tag", all(TAG in o["tags"] for o in with_line)),
        ("no option without the line has the tag", not any(TAG in o["tags"] for o in without)),
    ]
    results.record("alert-wilenski-waszyngtona", sc.spec["title"], "gtfs", {
        "alerted line": line, "options after": len(late), "options with the line": len(with_line),
        "titles": ", ".join(f"{o['title']} [{', '.join(o['tags'])}]" for o in late),
    }, checks)
    for name, ok in checks:
        assert ok, name
