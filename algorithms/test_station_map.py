"""Run from backend/: uv run pytest ../algorithms"""
from station_map import (
    group_rail_children, match_entrance, match_posts, match_rail_platform, overlay_hash, parse_platform_code,
)

LAT, LON = 52.23, 21.0
M = 0.000009  # about 1 m in latitude


def node(id_, dlat_m, dlon_m=0.0, **tags):
    return {"id": id_, "lat": LAT + dlat_m * M, "lon": LON + dlon_m * M * 1.63, "tags": tags}


def way(id_, points_m, **tags):
    return {"id": id_, "coords": [[LAT + a * M, LON + b * M * 1.63] for a, b in points_m], "tags": tags}


def test_posts_match_by_ref_within_50_m_and_prefer_platform_nodes():
    posts = [{"id": "ztm:435102", "raw_id": "435102", "lat": LAT, "lon": LON},
             {"id": "ztm:999901", "raw_id": "999901", "lat": LAT, "lon": LON},
             {"id": "ztm:000001", "raw_id": "000001", "lat": LAT, "lon": LON}]
    osm = [node(1, 20, ref="435102", public_transport="stop_position"),
           node(2, 8, ref="435102", public_transport="platform"),
           node(3, 120, ref="999901", public_transport="platform")]
    matched, mismatches = match_posts(posts, osm)
    assert matched["ztm:435102"]["osm_id"] == 2 and abs(matched["ztm:435102"]["distance_m"] - 8) < 1
    assert "ztm:999901" not in matched and mismatches == [{"id": "ztm:999901", "osm_id": 3, "distance_m": 120,
                                                           "why": "ref too far"}]
    assert "ztm:000001" not in matched  # no OSM object with that ref: silently GTFS


def test_platform_code_parsing_and_grouping():
    assert parse_platform_code("2 t. 20") == ("2", "20")
    assert parse_platform_code("1/2 t. 3") == ("1/2", "3")
    assert parse_platform_code("") is None and parse_platform_code("peron") is None
    kids = [{"id": "a", "code": "2 t. 20"}, {"id": "b", "code": "2 t. 22"}, {"id": "c", "code": "3 t. 21"},
            {"id": "f", "code": ""}]
    groups = group_rail_children(kids)
    assert [k["id"] for k in groups["2"]] == ["a", "b"] and [k["id"] for k in groups["3"]] == ["c"]
    assert [k["id"] for k in groups[None]] == ["f"]


def test_rail_platform_rules_in_order():
    ways = [way(1, [(0, -100), (0, 100)], railway="platform", local_ref="2", ref="20;22"),
            way(2, [(30, -100), (30, 100)], railway="platform", name="peron 3"),
            way(3, [(60, -100), (60, 100)], railway="platform", ref="5;7")]
    m = match_rail_platform(LAT, LON, "2", {"20", "22"}, ways)
    assert m["osm_id"] == 1 and m["matched_by"] == "local_ref" and m["distance_m"] < 1
    m = match_rail_platform(LAT + 30 * M, LON, "3", {"21"}, ways)
    assert m["osm_id"] == 2 and m["matched_by"] == "name"
    m = match_rail_platform(LAT + 60 * M, LON, "4", {"5"}, ways)
    assert m["osm_id"] == 3 and m["matched_by"] == "track"
    assert match_rail_platform(LAT, LON, "9", {"99"}, ways) is None


def test_rail_platform_too_far_is_not_matched():
    # the right number, but the way is 80 m away: GTFS stays (no fall-through to a weaker rule either)
    ways = [way(1, [(80, -100), (80, 100)], railway="platform", local_ref="2"),
            way(2, [(0, -100), (0, 100)], railway="platform", ref="20")]
    assert match_rail_platform(LAT, LON, "2", {"20"}, ways) is None


def test_entrance_nearest_within_30_m():
    ents = [node(1, 25), node(2, 10), node(3, 40)]
    assert match_entrance(LAT, LON, ents)["osm_id"] == 2
    assert match_entrance(LAT + 100 * M, LON, ents) is None


def test_overlay_hash_is_stable_and_sensitive():
    locs = [{"id": "a", "position": {"lat": 1.0, "lon": 2.0}}]
    h = overlay_hash(locs, {"walk": 1.3})
    assert h == overlay_hash([dict(locs[0])], {"walk": 1.3})
    assert h != overlay_hash(locs, {"walk": 1.0})
    assert h != overlay_hash([{"id": "a", "position": {"lat": 1.0, "lon": 2.1}}], {"walk": 1.3})
