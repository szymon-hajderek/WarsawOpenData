"""Place search covers the whole ZTM area (the routing area), not only Warsaw: e.g. Piaseczno (L-1, 709, 710)."""
import re

from app.api import geocode
from config import BBOX, REPO, in_bbox

PIASECZNO = (52.0717, 21.0262)
JANKI = (52.1407, 20.8939)  # L-1 terminus, west of the old Warsaw-only box


def _box(viewbox: str):
    left, top, right, bottom = map(float, viewbox.split(","))
    return (bottom, left, top, right)


def test_nominatim_viewbox_is_the_routing_area():
    assert _box(geocode.VIEWBOX) == BBOX
    for lat, lon in (PIASECZNO, JANKI):
        assert in_bbox(lat, lon, _box(geocode.VIEWBOX))


def test_frontend_viewbox_matches_the_backend():
    ts = (REPO / "frontend" / "src" / "api" / "geocode.ts").read_text()
    assert re.search(r"export const VIEWBOX = '([^']+)'", ts).group(1) == geocode.VIEWBOX
