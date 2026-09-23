"""
spatial.py — Spatial Consistency Checker for Weather Station Network
Feature: F7 — Spatial consistency checker (Phase 2)

Performs cross-station spatial consistency checks against k-nearest neighbor stations:
1. Projects spherical lat/lon coordinates to 3D Earth Cartesian space (R = 6371.0 km)
   and indexes stations using scipy.spatial.KDTree.
2. Performs batch queries for contemporaneous neighbor observations to prevent N+1 DB roundtrips.
3. Computes robust spatial z-score and departure from regional neighbor distribution.
4. Distinguishes single-station sensor anomalies (SPATIAL_MISMATCH) from genuine widespread
   regional extreme weather events (e.g. heatwaves, storm fronts).
"""

from datetime import datetime, timezone, timedelta
import math
from typing import List, Optional, Tuple, Dict, Any
import uuid

import numpy as np
from scipy.spatial import KDTree
from sqlalchemy.orm import Session

from storage.models import Station, RawReading, QCResult, QCVerdict


EARTH_RADIUS_KM = 6371.0


def lat_lon_to_cartesian(lat_deg: float, lon_deg: float, radius: float = EARTH_RADIUS_KM) -> Tuple[float, float, float]:
    """Convert spherical latitude/longitude in degrees to 3D Earth Cartesian coordinates (x, y, z) in kilometers."""
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)
    x = radius * math.cos(lat_rad) * math.cos(lon_rad)
    y = radius * math.cos(lat_rad) * math.sin(lon_rad)
    z = radius * math.sin(lat_rad)
    return x, y, z


class StationSpatialIndex:
    """Fast spatial nearest-neighbor index built on scipy.spatial.KDTree."""

    def __init__(self, stations: List[Station]):
        self.stations = stations
        self.station_map: Dict[uuid.UUID, Station] = {s.id: s for s in stations}
        self.station_codes: Dict[str, Station] = {s.station_code: s for s in stations}
        self.station_ids: List[uuid.UUID] = []
        self.coordinates: List[Tuple[float, float, float]] = []

        for st in stations:
            self.station_ids.append(st.id)
            self.coordinates.append(lat_lon_to_cartesian(st.latitude, st.longitude))

        if self.coordinates:
            self.tree = KDTree(np.array(self.coordinates))
        else:
            self.tree = None

    def find_k_nearest_neighbors(
        self,
        station_id: uuid.UUID,
        k: int = 5,
        max_distance_km: float = 150.0,
    ) -> List[Tuple[uuid.UUID, float]]:
        """
        Find up to k-nearest active neighbor stations within max_distance_km.
        Excludes the target station itself.
        Returns list of (neighbor_station_id, distance_km).
        """
        if self.tree is None or len(self.station_ids) <= 1:
            return []

        try:
            target_idx = self.station_ids.index(station_id)
        except ValueError:
            return []

        target_coord = self.coordinates[target_idx]
        
        # Query k + 1 because the target station itself will be the closest point (distance = 0)
        query_k = min(len(self.station_ids), k + 1)
        distances, indices = self.tree.query(target_coord, k=query_k)

        if np.isscalar(distances):
            distances = [distances]
            indices = [indices]

        neighbors: List[Tuple[uuid.UUID, float]] = []
        for dist, idx in zip(distances, indices):
            neighbor_id = self.station_ids[idx]
            if neighbor_id != station_id and dist <= max_distance_km:
                neighbors.append((neighbor_id, float(dist)))
                if len(neighbors) == k:
                    break

        return neighbors


def check_spatial_consistency(
    target_value: Optional[float],
    neighbor_values: List[float],
    min_neighbors: int = 2,
    z_threshold: float = 3.0,
    min_delta: float = 3.5,
    min_std: float = 1.0,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Pure function: evaluate spatial consistency of a sensor value against contemporaneous neighbor readings.
    
    Returns:
    - is_anomalous: bool
    - reason_code: 'SPATIAL_MISMATCH' | 'SPATIAL_CONSISTENT' | 'SPATIAL_INSUFFICIENT_DATA'
    - details: breakdown of neighbor statistics, z-score, and spatial delta.
    """
    if target_value is None or math.isnan(target_value):
        return False, "SPATIAL_INSUFFICIENT_DATA", {"reason": "target_value_missing"}

    # Filter valid non-null finite neighbor readings
    valid_neighbors = [float(v) for v in neighbor_values if v is not None and not math.isnan(v)]

    if len(valid_neighbors) < min_neighbors:
        return False, "SPATIAL_INSUFFICIENT_DATA", {
            "reason": "insufficient_neighbor_readings",
            "available_neighbors": len(valid_neighbors),
            "required_min": min_neighbors,
        }

    neighbor_mean = float(np.mean(valid_neighbors))
    # Minimum standard deviation floor prevents division by zero when neighbors are identical
    raw_std = float(np.std(valid_neighbors))
    neighbor_std = max(raw_std, min_std)

    delta = abs(target_value - neighbor_mean)
    z_score = delta / neighbor_std

    details = {
        "target_value": round(target_value, 3),
        "neighbor_mean": round(neighbor_mean, 3),
        "neighbor_std": round(neighbor_std, 3),
        "spatial_delta": round(delta, 3),
        "z_score": round(z_score, 3),
        "z_threshold": z_threshold,
        "min_delta_required": min_delta,
        "neighbor_count": len(valid_neighbors),
        "neighbor_values": [round(v, 2) for v in valid_neighbors],
    }

    if z_score >= z_threshold and delta >= min_delta:
        # Isolated deviation beyond neighbor spread -> sensor fault!
        return True, "SPATIAL_MISMATCH", details

    # Within neighbor spread or neighbors also experiencing extreme event -> consistent!
    return False, "SPATIAL_CONSISTENT", details


# Module-level spatial index cache
_SPATIAL_INDEX_CACHE: Optional[StationSpatialIndex] = None


def get_spatial_index(db: Session, force_refresh: bool = False) -> StationSpatialIndex:
    """Retrieve or build the StationSpatialIndex from registered database stations."""
    global _SPATIAL_INDEX_CACHE
    stations = db.query(Station).all()
    current_ids = {s.id for s in stations}
    if (
        _SPATIAL_INDEX_CACHE is None
        or force_refresh
        or set(_SPATIAL_INDEX_CACHE.station_map.keys()) != current_ids
    ):
        _SPATIAL_INDEX_CACHE = StationSpatialIndex(stations)
    return _SPATIAL_INDEX_CACHE


def evaluate_spatial_for_reading(
    db: Session,
    reading: RawReading,
    station: Station,
    variable: str = "temperature",
    k: int = 5,
    max_distance_km: float = 150.0,
    z_threshold: float = 3.0,
    min_delta: float = 3.5,
) -> Optional[QCResult]:
    """
    Evaluate spatial consistency for a given reading against its k-nearest neighbors.
    Batch-queries contemporaneous neighbor readings at the exact timestamp.
    """
    spatial_index = get_spatial_index(db)
    target_val = getattr(reading, variable, None)
    if target_val is None or math.isnan(target_val):
        return None

    neighbors = spatial_index.find_k_nearest_neighbors(
        station_id=station.id,
        k=k,
        max_distance_km=max_distance_km,
    )

    if not neighbors:
        return QCResult(
            reading_id=reading.id,
            station_id=station.id,
            variable=variable,
            verdict=QCVerdict.valid,
            reason_code="SPATIAL_INSUFFICIENT_DATA",
            fault_type=None,
            confidence=0.50,
            details={"reason": "no_neighbors_within_distance", "max_distance_km": max_distance_km},
        )

    neighbor_ids = [nid for nid, _ in neighbors]

    # Batch query neighbor readings at same timestamp (zero N+1 queries)
    neighbor_readings = (
        db.query(RawReading)
        .filter(
            RawReading.station_id.in_(neighbor_ids),
            RawReading.timestamp == reading.timestamp,
        )
        .all()
    )

    neighbor_values = [
        getattr(nr, variable)
        for nr in neighbor_readings
        if getattr(nr, variable, None) is not None
    ]

    is_anom, reason_code, details = check_spatial_consistency(
        target_value=target_val,
        neighbor_values=neighbor_values,
        min_neighbors=2,
        z_threshold=z_threshold,
        min_delta=min_delta,
    )

    verdict = QCVerdict.anomalous if is_anom else QCVerdict.valid
    fault_type = "spatial_inconsistency" if is_anom else None
    confidence = 0.95 if is_anom else 0.90

    return QCResult(
        reading_id=reading.id,
        station_id=station.id,
        variable=variable,
        verdict=verdict,
        reason_code=reason_code,
        fault_type=fault_type,
        confidence=confidence,
        details=details,
    )


def run_spatial_qc_for_reading(
    db: Session,
    reading_id: int,
    variables: Optional[List[str]] = None,
) -> List[QCResult]:
    """
    Service helper: evaluates and persists spatial QCResult rows for a reading.
    """
    reading = db.query(RawReading).filter(RawReading.id == reading_id).first()
    if not reading:
        raise ValueError(f"RawReading with id {reading_id} not found.")

    station = db.query(Station).filter(Station.id == reading.station_id).first()
    if not station:
        raise ValueError(f"Station with id {reading.station_id} not found.")

    check_vars = variables or ["temperature", "humidity"]
    results: List[QCResult] = []

    for var in check_vars:
        qc_res = evaluate_spatial_for_reading(db, reading, station, variable=var)
        if qc_res:
            results.append(qc_res)
            db.add(qc_res)

    if results:
        db.commit()
        for r in results:
            db.refresh(r)

    return results
