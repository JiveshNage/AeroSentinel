# AeroSentinel Map Assets & Offline OpenStreetMap Guide

This directory contains map boundary definitions, station metadata, and assets for AeroSentinel's spatial monitoring and Leaflet mapping engine.

---

## 1. Why did the initial OpenStreetMap export (`asset/map`) error?
The file `asset/map` was exported via OpenStreetMap's standard web interface for the bounding box:
- **South-West:** `43.04° N, -18.76° W`
- **North-East:** `58.63° N, 18.59° E`

This region spans the entire sub-continent of **Western & Central Europe** (United Kingdom, Ireland, France, Germany, Netherlands, Belgium, Luxembourg, Switzerland, and parts of Spain/Italy). 

OpenStreetMap's live web export tool enforces a limit of **0.25 square degrees** (~50,000 nodes). Because this query covered **~570 square degrees**, the Overpass API server exceeded its live query RAM limit and output:
```xml
<remark> runtime error: Query run out of memory using about 2048 MB of RAM. </remark>
```

---

## 2. Validated Offline Map Files Provided

To enable offline mapping, spatial visualization, and feature extraction for this area, we have generated valid companion files:

| File | Format | Description |
| :--- | :--- | :--- |
| `asset/map.geojson` | GeoJSON | Contains the bounding polygon coverage zone + key validated meteorological AWS stations (Berlin, London Heathrow, Paris Montsouris, Amsterdam Schiphol, Frankfurt, Dublin). |
| `asset/map.osm` | OSM XML | Clean, valid OpenStreetMap XML representation with nodes, tags (`amenity=weather_station`), and elevation metadata. |
| `asset/Logo.png` | PNG | Official AeroSentinel brand emblem. |

---

## 3. How to Obtain Complete Raw OSM Vector Data (`.osm.pbf`)

If you require the complete, uncompressed raw OpenStreetMap dataset (all roads, coastlines, buildings, and land use):

### Option A: Official Pre-Built Country Extracts (Geofabrik)
Geofabrik provides daily-updated, validated `.osm.pbf` extracts:
- **Great Britain:** [great-britain-latest.osm.pbf](https://download.geofabrik.de/europe/great-britain-latest.osm.pbf) (~1.7 GB)
- **Germany:** [germany-latest.osm.pbf](https://download.geofabrik.de/europe/germany-latest.osm.pbf) (~4.2 GB)
- **France:** [france-latest.osm.pbf](https://download.geofabrik.de/europe/france-latest.osm.pbf) (~4.5 GB)
- **Ireland & Northern Ireland:** [ireland-and-northern-ireland-latest.osm.pbf](https://download.geofabrik.de/europe/ireland-and-northern-ireland-latest.osm.pbf) (~380 MB)
- **Complete Europe Extract:** [europe-latest.osm.pbf](https://download.geofabrik.de/europe-latest.osm.pbf) (~28 GB)

### Option B: Custom Bounding Box Extract (BBBike Service)
To extract this exact bounding box as a single `.osm.pbf` file without running out of RAM:
- [BBBike Custom Extractor Link](https://extract.bbbike.org/?sw_lng=-18.76&sw_lat=43.04&ne_lng=18.59&ne_lat=58.63&format=osm.pbf)

---

## 4. Offline Map Tiles in Leaflet

Leaflet renders maps using image tiles (`/tiles/{z}/{x}/{y}.png`). 
We have automated the offline tile packager in:
```bash
python Dataset/osm_offline_helper.py --tiles
```
- Tile packages are saved into `frontend/public/tiles/{z}/{x}/{y}.png`.
- In the AeroSentinel dashboard, click the **"Offline"** basemap button in the top-right toolbar to browse maps completely disconnected from the internet!
