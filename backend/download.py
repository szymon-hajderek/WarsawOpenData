"""Download raw data into data/. Usage (from backend/): uv run python download.py [mkuran|um_warszawa|nextbike|osm]"""
import sys

from sources import mkuran, nextbike, osm, um_warszawa

MODULES = {"mkuran": mkuran, "um_warszawa": um_warszawa, "nextbike": nextbike, "osm": osm}

if __name__ == "__main__":
    for name in sys.argv[1:] or MODULES:
        print(name, MODULES[name].download())
