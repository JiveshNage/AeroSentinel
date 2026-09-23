"""
test_fault_injector.py — Unit and integration tests for F5 Fault Injection Tool

Tests:
1. Flatline: produces exactly N identical consecutive values
2. Spike: deviates from normal by configured magnitude (positive and negative)
3. Drift: accumulates monotonically over time (delta >= 0 throughout duration)
4. Dropout: produces missing timestamps (missing rows) or NaN values, NEVER zero
5. Spatial Inconsistency: alters target station without modifying neighboring stations
6. Plausible Extreme Weather: alters all regional stations simultaneously and is flagged as NOT anomalous
7. Benchmark Dataset: generates complete labeled dataset for downstream ML (F6/F8)
8. Visual Spotcheck Plot: generates valid 4-panel image file
"""

import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from qc.fault_injector import (
    inject_flatline,
    inject_spike,
    inject_drift,
    inject_dropout,
    inject_spatial_inconsistency,
    inject_plausible_extreme_weather,
    generate_labeled_benchmark_dataset,
    plot_injected_faults,
)
from ingestion.simulator import generate_synthetic_weather_stream
from storage.models import Station


@pytest.fixture
def clean_single_station_df():
    """Generates 48 hours of clean hourly synthetic weather data for one station."""
    st = Station(station_code="DEL001", name="Safdarjung", latitude=28.58, longitude=77.20, elevation_m=216.0)
    base_time = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    return generate_synthetic_weather_stream([st], start_time=base_time, hours=48)


@pytest.fixture
def clean_multi_station_df():
    """Generates 48 hours of clean hourly synthetic weather data for 5 stations."""
    stations = [
        Station(station_code=f"NCR00{i}", name=f"NCR Station {i}", latitude=28.5 + (i * 0.05), longitude=77.2 + (i * 0.05), elevation_m=210.0)
        for i in range(1, 6)
    ]
    base_time = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    return generate_synthetic_weather_stream(stations, start_time=base_time, hours=48)


def test_inject_flatline_produces_identical_consecutive_values(clean_single_station_df):
    """Assert injected flatline produces exactly N identical consecutive values."""
    start_idx = 10
    duration = 8
    df = clean_single_station_df.copy()
    initial_temps = df["temperature"].values.copy()

    # The clean baseline has diurnal variation, so values in this window are not all identical
    assert len(set(initial_temps[start_idx : start_idx + duration])) > 1

    injected = inject_flatline(df, variable="temperature", station_id="DEL001", start_idx=start_idx, duration=duration)

    fault_vals = injected["temperature"].iloc[start_idx : start_idx + duration].values
    assert len(fault_vals) == duration
    # All N values must be strictly equal
    assert len(set(fault_vals)) == 1
    assert fault_vals[0] == initial_temps[start_idx]

    # Verify metadata columns
    assert (injected["is_anomalous"].iloc[start_idx : start_idx + duration] == True).all()
    assert (injected["fault_type"].iloc[start_idx : start_idx + duration] == "flatline").all()
    assert (injected["fault_variable"].iloc[start_idx : start_idx + duration] == "temperature").all()

    # Outside the fault window, values should be untouched
    assert np.allclose(injected["temperature"].iloc[:start_idx], initial_temps[:start_idx])
    assert np.allclose(injected["temperature"].iloc[start_idx + duration :], initial_temps[start_idx + duration :])


def test_inject_flatline_custom_freeze_value(clean_single_station_df):
    """Assert injected flatline can freeze at an explicit configured value."""
    injected = inject_flatline(clean_single_station_df, variable="temperature", start_idx=5, duration=4, freeze_value=25.0)
    fault_vals = injected["temperature"].iloc[5 : 9].values
    assert (fault_vals == 25.0).all()


def test_inject_spike_magnitude_and_duration(clean_single_station_df):
    """Assert injected spike is outside normal baseline by the exact configured magnitude."""
    idx = 14
    magnitude = 18.5
    orig_temp = clean_single_station_df["temperature"].iloc[idx]

    injected = inject_spike(clean_single_station_df, variable="temperature", idx=idx, magnitude=magnitude, duration=1)

    spiked_temp = injected["temperature"].iloc[idx]
    assert np.isclose(spiked_temp, orig_temp + magnitude)
    assert injected["is_anomalous"].iloc[idx] == True
    assert injected["fault_type"].iloc[idx] == "spike"
    assert injected["fault_variable"].iloc[idx] == "temperature"

    # Pre and post values unchanged
    assert np.isclose(injected["temperature"].iloc[idx - 1], clean_single_station_df["temperature"].iloc[idx - 1])
    assert np.isclose(injected["temperature"].iloc[idx + 1], clean_single_station_df["temperature"].iloc[idx + 1])


def test_inject_negative_spike(clean_single_station_df):
    """Assert negative spike (e.g. sudden drop in humidity) works accurately."""
    idx = 20
    magnitude = -35.0
    orig_hum = clean_single_station_df["humidity"].iloc[idx]

    injected = inject_spike(clean_single_station_df, variable="humidity", idx=idx, magnitude=magnitude, duration=2)

    assert np.isclose(injected["humidity"].iloc[idx], orig_hum + magnitude)
    assert np.isclose(injected["humidity"].iloc[idx + 1], clean_single_station_df["humidity"].iloc[idx + 1] + magnitude)
    assert injected["fault_type"].iloc[idx] == "spike"
    assert injected["fault_variable"].iloc[idx] == "humidity"


def test_inject_drift_accumulates_monotonically(clean_single_station_df):
    """Assert injected drift accumulates monotonically over time."""
    start_idx = 8
    duration = 20
    total_drift = 10.0

    injected = inject_drift(
        clean_single_station_df,
        variable="temperature",
        start_idx=start_idx,
        duration=duration,
        total_drift=total_drift,
    )

    orig_segment = clean_single_station_df["temperature"].iloc[start_idx : start_idx + duration].values
    drifted_segment = injected["temperature"].iloc[start_idx : start_idx + duration].values
    offsets = drifted_segment - orig_segment

    # Offsets must start at 0 and end at total_drift
    assert np.isclose(offsets[0], 0.0)
    assert np.isclose(offsets[-1], total_drift)

    # Monotonic accumulation: consecutive offset deltas must be >= 0
    offset_diffs = np.diff(offsets)
    assert (offset_diffs >= -1e-9).all()
    # Confirm strictly increasing progression
    assert (offset_diffs > 0).all()

    # Metadata check
    assert (injected["is_anomalous"].iloc[start_idx : start_idx + duration] == True).all()
    assert (injected["fault_type"].iloc[start_idx : start_idx + duration] == "drift").all()


def test_inject_dropout_missing_rows(clean_single_station_df):
    """Assert dropout as missing rows removes timestamps, never zero-fills."""
    start_idx = 12
    duration = 6
    orig_len = len(clean_single_station_df)

    injected = inject_dropout(
        clean_single_station_df,
        station_id="DEL001",
        start_idx=start_idx,
        duration=duration,
        as_missing_rows=True,
    )

    # Length must be reduced exactly by duration
    assert len(injected) == orig_len - duration
    # Missing timestamps: time difference across gap should be (duration + 1) hours
    times = pd.to_datetime(injected["timestamp"]).reset_index(drop=True)
    time_diff = times.iloc[start_idx] - times.iloc[start_idx - 1]
    assert time_diff == timedelta(hours=duration + 1)


def test_inject_dropout_nan_values_never_zero(clean_single_station_df):
    """Assert dropout as sensor disconnection injects NaN/null, NEVER 0.0 values."""
    start_idx = 10
    duration = 5
    injected = inject_dropout(
        clean_single_station_df,
        station_id="DEL001",
        start_idx=start_idx,
        duration=duration,
        as_missing_rows=False,
        variable="temperature",
    )

    dropped_vals = injected["temperature"].iloc[start_idx : start_idx + duration]
    # Must be NaN / null
    assert dropped_vals.isna().all()
    # Must NOT be 0.0
    for val in dropped_vals:
        assert val != 0.0 and math.isnan(val)

    assert (injected["fault_type"].iloc[start_idx : start_idx + duration] == "dropout").all()


def test_inject_spatial_inconsistency_targets_single_station(clean_multi_station_df):
    """Assert spatial inconsistency only modifies the target station while neighbors stay intact."""
    df = clean_multi_station_df.copy()
    target_st = "NCR002"
    other_st = "NCR001"

    injected = inject_spatial_inconsistency(
        df,
        target_station_id=target_st,
        variable="temperature",
        start_idx=15,
        magnitude=14.0,
        duration=4,
    )

    # Target station has anomalous rows
    target_slice = injected[injected["station_id"] == target_st]
    assert target_slice["is_anomalous"].any()

    # Other station must remain completely unaffected and non-anomalous
    other_orig = clean_multi_station_df[clean_multi_station_df["station_id"] == other_st]["temperature"].values
    other_after = injected[injected["station_id"] == other_st]["temperature"].values
    assert np.allclose(other_orig, other_after)
    assert not injected[injected["station_id"] == other_st]["is_anomalous"].fillna(False).any()


def test_inject_plausible_extreme_weather_affects_all_and_is_not_anomalous(clean_multi_station_df):
    """
    Assert plausible extreme weather affects ALL stations regionally,
    and ground truth labels it as NOT anomalous (is_anomalous=False).
    This is the core test case for F7 spatial consistency checker.
    """
    df = clean_multi_station_df.copy()
    delta = 7.5
    hours = 6

    start_dt = datetime(2024, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    injected = inject_plausible_extreme_weather(
        df,
        variable="temperature",
        start_time=start_dt,
        duration_hours=hours,
        delta=delta,
    )

    injected["dt"] = pd.to_datetime(injected["timestamp"])
    event_mask = (injected["dt"] >= start_dt) & (injected["dt"] < start_dt + timedelta(hours=hours))

    # All stations in the region must experience temperature increase
    event_rows = injected[event_mask]
    stations_in_event = event_rows["station_id"].unique()
    assert len(stations_in_event) == 5

    # Ground truth: is_anomalous MUST be False
    assert (event_rows["is_anomalous"] == False).all()
    assert (event_rows["fault_type"] == "plausible_extreme").all()


def test_generate_labeled_benchmark_dataset(clean_multi_station_df):
    """Assert multi-station benchmark dataset contains all 4 fault types + valid baseline."""
    labeled_df = generate_labeled_benchmark_dataset(clean_multi_station_df, seed=42)

    # Check that required columns exist
    assert "is_anomalous" in labeled_df.columns
    assert "fault_type" in labeled_df.columns
    assert "fault_variable" in labeled_df.columns

    fault_types = set(labeled_df["fault_type"].dropna().unique())
    # Must contain valid, flatline, spike, drift, and dropout
    assert "valid" in fault_types
    assert "flatline" in fault_types
    assert "spike" in fault_types
    assert "drift" in fault_types
    assert "dropout" in fault_types

    # Ensure anomalous flag aligns with fault types
    anom_rows = labeled_df[labeled_df["is_anomalous"] == True]
    assert len(anom_rows) > 0
    assert "valid" not in anom_rows["fault_type"].values


def test_plot_injected_faults_generates_image(clean_single_station_df, tmp_path):
    """Assert plot_injected_faults renders a 4-panel visual plot to disk."""
    clean_df = clean_single_station_df.copy()
    flatline_df = inject_flatline(clean_df, variable="temperature", start_idx=10, duration=6)
    spike_df = inject_spike(clean_df, variable="temperature", idx=15, magnitude=12.0)
    drift_df = inject_drift(clean_df, variable="temperature", start_idx=8, duration=16, total_drift=8.0)
    dropout_df = inject_dropout(clean_df, station_id="DEL001", start_idx=12, duration=4, as_missing_rows=False)

    out_file = tmp_path / "test_fault_plot.png"
    result_path = plot_injected_faults(
        clean_series=clean_df["temperature"],
        flatline_series=flatline_df["temperature"],
        spike_series=spike_df["temperature"],
        drift_series=drift_df["temperature"],
        dropout_series=dropout_df["temperature"],
        output_path=out_file,
    )

    assert result_path.exists()
    assert result_path.stat().st_size > 10000  # PNG image should be at least 10KB
