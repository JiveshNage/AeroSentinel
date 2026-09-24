"""
osm_offline_helper.py — AeroSentinel (SIH26073)
Tool for downloading and managing offline OpenStreetMap / Carto data and Leaflet map tiles
for the bounding box specified in asset/map:
    minlat: 43.04, minlon: -18.76, maxlat: 58.63, maxlon: 18.59
    (Covers Western & Central Europe: UK, Ireland, France, Germany, Benelux)
"""

import math
import os
import sys
import time
from pathlib import Path
from typing import Tuple, List

import requests

# Bounding box extracted from asset/map
BBOX = {
    "minlat": 43.04,
    "minlon": -18.76,
    "maxlat": 58.63,
    "maxlon": 18.59,
}

CARTO_KEY = "cb1_3wto_1_98681061742df32c284b0e0b"

# Official Geofabrik daily OSM PBF downloads covering this region
GEOFABRIK_EXTRACTS = {
    "Great Britain": "https://download.geofabrik.de/europe/great-britain-latest.osm.pbf",
    "Ireland & Northern Ireland": "https://download.geofabrik.de/europe/ireland-and-northern-ireland-latest.osm.pbf",
    "Germany": "https://download.geofabrik.de/europe/germany-latest.osm.pbf",
    "France": "https://download.geofabrik.de/europe/france-latest.osm.pbf",
    "Netherlands": "https://download.geofabrik.de/europe/netherlands-latest.osm.pbf",
    "Belgium": "https://download.geofabrik.de/europe/belgium-latest.osm.pbf",
    "Europe (Complete 28 GB)": "https://download.geofabrik.de/europe-latest.osm.pbf",
}

# BBBike Custom Area Extractor URL
BBBIKE_CUSTOM_EXTRACT_URL = (
    f"https://extract.bbbike.org/?sw_lng={BBOX['minlon']}&sw_lat={BBOX['minlat']}"
    f"&ne_lng={BBOX['maxlon']}&ne_lat={BBOX['maxlat']}&format=osm.pbf"
)


def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    """Convert latitude/longitude to OSM slippy map tile numbers (x, y)."""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def get_tile_range(bbox: dict, zoom: int) -> Tuple[range, range]:
    """Return the range of tile X and Y coordinates for a given bbox and zoom level."""
    x_min, y_max = deg2num(bbox["minlat"], bbox["minlon"], zoom)
    x_max, y_min = deg2num(bbox["maxlat"], bbox["maxlon"], zoom)
    x_range = range(min(x_min, x_max), max(x_min, x_max) + 1)
    y_range = range(min(y_min, y_max), max(y_min, y_max) + 1)
    return x_range, y_range


def download_offline_tiles(
    output_dir: str = "frontend/public/tiles",
    min_zoom: int = 4,
    max_zoom: int = 6,
    tile_url_template: str = f"https://basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}.png?key={CARTO_KEY}",
):
    """
    Download raster map tiles for the bounding box so the Leaflet map can work 100% offline.
    """
    out_path = Path(output_dir)
    total_tiles = 0
    tile_list = []

    for z in range(min_zoom, max_zoom + 1):
        xr, yr = get_tile_range(BBOX, z)
        for x in xr:
            for y in yr:
                tile_list.append((z, x, y))
                total_tiles += 1

    print(f"[*] Preparing to download {total_tiles} offline tiles (Zooms {min_zoom} to {max_zoom})...")
    print(f"    Destination: {out_path.resolve()}")

    session = requests.Session()
    session.headers.update({"User-Agent": "AeroSentinel/1.0 (academic research)"})
    success_count = 0

    for idx, (z, x, y) in enumerate(tile_list, 1):
        tile_file = out_path / str(z) / str(x) / f"{y}.png"
        if tile_file.exists() and tile_file.stat().st_size > 100:
            success_count += 1
            continue

        tile_file.parent.mkdir(parents=True, exist_ok=True)
        url = tile_url_template.format(z=z, x=x, y=y)

        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                tile_file.write_bytes(resp.content)
                success_count += 1
            else:
                print(f"    [!] HTTP {resp.status_code} for tile {z}/{x}/{y}")
            if idx % 10 == 0 or idx == total_tiles:
                print(f"    Progress: {idx}/{total_tiles} tiles downloaded ({idx*100//total_tiles}%)")
            time.sleep(0.04)
        except Exception as e:
            print(f"    [!] Failed to download tile {z}/{x}/{y}: {e}")

    print(f"[✓] Completed offline tile download: {success_count}/{total_tiles} tiles saved in {out_path}")


def print_complete_osm_extract_guide():
    """Display download instructions for complete raw vector OSM data."""
    print("=" * 70)
    print("COMPLETE OPENSTREETMAP DATA EXTRACTION GUIDE")
    print("=" * 70)
    print(f"Target Bounding Box (from asset/map):")
    print(f"  Latitude:  {BBOX['minlat']}° to {BBOX['maxlat']}°")
    print(f"  Longitude: {BBOX['minlon']}° to {BBOX['maxlon']}°")
    print("\nWhy did the standard OpenStreetMap 'Export' button fail?")
    print("  -> Raw XML export for this bounding box spans 7+ countries across Western Europe.")
    print("  -> The live OSM API limit is 0.25 sq degrees. This box is ~570 sq degrees!")
    print("  -> The Overpass server aborted with: 'Query run out of memory using about 2048 MB'.")
    print("\nHOW TO GET COMPLETE OFFLINE OSM DATA FOR THIS REGION:")
    print("-" * 70)
    print("Option 1: Download pre-built Country Extracts (.osm.pbf format)")
    for name, url in GEOFABRIK_EXTRACTS.items():
        print(f"  • {name:28}: {url}")

    print("\nOption 2: Request an exact custom bbox extract via BBBike (free service):")
    print(f"  Link: {BBBIKE_CUSTOM_EXTRACT_URL}")

    print("\nOption 3: Download offline Leaflet tiles for local offline rendering:")
    print("  Run: python Dataset/osm_offline_helper.py --tiles --min-zoom 4 --max-zoom 6")
    print("=" * 70)


if __name__ == "__main__":
    if "--tiles" in sys.argv:
        download_offline_tiles()
    else:
        print_complete_osm_extract_guide()
