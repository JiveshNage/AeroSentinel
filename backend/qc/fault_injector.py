"""
fault_injector.py — AeroSentinel Sensor Fault Injection Tool
Feature: F5 — Fault injection tool (Phase 1)

Injects parameterized synthetic sensor faults into clean Automatic Weather Station (AWS)
time series for ML training, spatial-consistency evaluation, and judge demonstrations:
- Flatline (sensor stuck / frozen values)
- Spike (electrical / transient outlier pulse)
- Drift (slow calibration decay / linear bias ramp)
- Dropout (telemetry / hardware loss: missing timestamps, NOT zero values)
- Spatial inconsistency (single station fault vs clean neighbors)
- Plausible extreme weather (regional event across all stations, NOT a fault)

Usage:
    python -m qc.fault_injector --demo-plot --output reports/injected_faults_spotcheck.png
"""

import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import copy

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt


def inject_flatline(
    df: pd.DataFrame,
    variable: str = "temperature",
    station_id: Optional[str] = None,
    start_idx: int = 12,
    duration: int = 8,
    freeze_value: Optional[float] = None,
) -> pd.DataFrame:
    """
    Inject flatline fault: freeze sensor reading to a constant value for N consecutive intervals.
    Per test.md: actually produces N identical consecutive values.
    """
    out = df.copy()
    mask = (out["station_id"] == station_id) if station_id else pd.Series(True, index=out.index)
    indices = out[mask].index

    if len(indices) <= start_idx:
        return out

    inject_indices = indices[start_idx : start_idx + duration]
    val = freeze_value if freeze_value is not None else out.loc[inject_indices[0], variable]

    out.loc[inject_indices, variable] = val
    out.loc[inject_indices, "is_anomalous"] = True
    out.loc[inject_indices, "fault_type"] = "flatline"
    out.loc[inject_indices, "fault_variable"] = variable
    return out


def inject_spike(
    df: pd.DataFrame,
    variable: str = "temperature",
    station_id: Optional[str] = None,
    idx: int = 15,
    magnitude: float = 16.0,
    duration: int = 1,
) -> pd.DataFrame:
    """
    Inject spike fault: sudden implausible deviation added for 1-2 intervals.
    Per test.md: injected spike is outside normal range by configured magnitude.
    """
    out = df.copy()
    mask = (out["station_id"] == station_id) if station_id else pd.Series(True, index=out.index)
    indices = out[mask].index

    if len(indices) <= idx:
        return out

    inject_indices = indices[idx : idx + duration]
    out.loc[inject_indices, variable] = out.loc[inject_indices, variable] + magnitude
    out.loc[inject_indices, "is_anomalous"] = True
    out.loc[inject_indices, "fault_type"] = "spike"
    out.loc[inject_indices, "fault_variable"] = variable
    return out


def inject_drift(
    df: pd.DataFrame,
    variable: str = "temperature",
    station_id: Optional[str] = None,
    start_idx: int = 10,
    duration: int = 24,
    total_drift: float = 9.0,
) -> pd.DataFrame:
    """
    Inject calibration drift: monotonically accumulating linear offset over time.
    Per test.md: injected drift accumulates monotonically.
    """
    out = df.copy()
    mask = (out["station_id"] == station_id) if station_id else pd.Series(True, index=out.index)
    indices = out[mask].index

    if len(indices) <= start_idx:
        return out

    actual_duration = min(duration, len(indices) - start_idx)
    inject_indices = indices[start_idx : start_idx + actual_duration]

    offsets = np.linspace(0.0, total_drift, actual_duration)
    out.loc[inject_indices, variable] = out.loc[inject_indices, variable] + offsets
    out.loc[inject_indices, "is_anomalous"] = True
    out.loc[inject_indices, "fault_type"] = "drift"
    out.loc[inject_indices, "fault_variable"] = variable
    return out


def inject_dropout(
    df: pd.DataFrame,
    station_id: str,
    start_idx: int = 14,
    duration: int = 6,
    as_missing_rows: bool = True,
    variable: Optional[str] = None,
) -> pd.DataFrame:
    """
    Inject telemetry dropout: sensor or transmission failure.
    Per test.md: produces missing timestamps (or nulls), NEVER zero values!
    """
    out = df.copy()
    mask = out["station_id"] == station_id
    indices = out[mask].index

    if len(indices) <= start_idx:
        return out

    drop_indices = indices[start_idx : start_idx + duration]

    if as_missing_rows:
        # Physical dropout: station drops off telemetry stream completely (missing rows)
        out = out.drop(index=drop_indices)
    else:
        # Sensor disconnection: variable reports NaN/null, not zero
        target_var = variable if variable else "temperature"
        out.loc[drop_indices, target_var] = np.nan
        out.loc[drop_indices, "is_anomalous"] = True
        out.loc[drop_indices, "fault_type"] = "dropout"
        out.loc[drop_indices, "fault_variable"] = target_var

    return out


def inject_spatial_inconsistency(
    df: pd.DataFrame,
    target_station_id: str,
    variable: str = "temperature",
    start_idx: int = 15,
    magnitude: float = 14.0,
    duration: int = 5,
) -> pd.DataFrame:
    """
    Single-station sensor fault: only target_station deviates, while neighboring
    stations follow the natural regional weather pattern.
    """
    return inject_spike(
        df=df,
        variable=variable,
        station_id=target_station_id,
        idx=start_idx,
        magnitude=magnitude,
        duration=duration,
    )


def inject_plausible_extreme_weather(
    df: pd.DataFrame,
    variable: str = "temperature",
    start_time: datetime = None,
    duration_hours: int = 6,
    delta: float = 8.0,
) -> pd.DataFrame:
    """
    Genuine regional weather event (e.g. severe heatwave or cold front):
    Affects ALL stations in the regional cluster simultaneously.
    Ground truth: NOT a sensor fault (is_anomalous=False, fault_type="plausible_extreme").
    This is what tests the spatial-consistency checker (F7).
    """
    out = df.copy()
    out["dt"] = pd.to_datetime(out["timestamp"])

    if start_time is None:
        start_time = out["dt"].min() + timedelta(hours=12)

    end_time = start_time + timedelta(hours=duration_hours)
    mask = (out["dt"] >= start_time) & (out["dt"] < end_time)

    out.loc[mask, variable] = out.loc[mask, variable] + delta
    out.loc[mask, "is_anomalous"] = False
    out.loc[mask, "fault_type"] = "plausible_extreme"
    return out.drop(columns=["dt"])


def plot_injected_faults(
    clean_series: pd.Series,
    flatline_series: pd.Series,
    spike_series: pd.Series,
    drift_series: pd.Series,
    dropout_series: pd.Series,
    output_path: Path,
    title: str = "AeroSentinel Fault Injection Patterns (Temperature °C)",
) -> Path:
    """
    Generate professional 4-panel visual verification plot spot-checking
    the 4 primary sensor fault types against the clean ground truth baseline.
    """
    fig, axes = plt.subplots(4, 1, figsize=(10, 9), sharex=True)
    plt.subplots_adjust(hspace=0.35)

    x = range(len(clean_series))

    # Color palette adhering to design.md tokens
    c_clean = "#1D4E5F"       # --accent (teal)
    c_fault = "#C1443C"       # --status-anomalous (brick red)
    c_grid = "#D8DCE0"        # --line
    c_text = "#10161C"        # --ink
    c_muted = "#5B6670"       # --muted

    # Panel 1: Flatline (Frozen Sensor)
    axes[0].plot(x, clean_series, color=c_clean, linestyle="--", alpha=0.5, label="Clean Baseline")
    axes[0].plot(x, flatline_series, color=c_fault, linewidth=2.0, label="Flatline Injected")
    axes[0].set_title("1. Flatline Fault (Sensor Stuck / Fixed Value for 8h)", fontsize=11, fontweight="bold", color=c_text, loc="left")
    axes[0].set_ylabel("Temp (°C)", fontsize=9, color=c_muted)
    axes[0].grid(True, linestyle=":", color=c_grid)
    axes[0].legend(loc="upper right", fontsize=8)

    # Panel 2: Spike (Transient Impulse Outlier)
    axes[1].plot(x, clean_series, color=c_clean, linestyle="--", alpha=0.5, label="Clean Baseline")
    axes[1].plot(x, spike_series, color=c_fault, linewidth=1.8, marker="o", markersize=4, label="Spike Injected (+16°C)")
    axes[1].set_title("2. Spike Fault (Electrical Noise / Voltage Surge Impulse)", fontsize=11, fontweight="bold", color=c_text, loc="left")
    axes[1].set_ylabel("Temp (°C)", fontsize=9, color=c_muted)
    axes[1].grid(True, linestyle=":", color=c_grid)
    axes[1].legend(loc="upper right", fontsize=8)

    # Panel 3: Drift (Slow Calibration Decay)
    axes[2].plot(x, clean_series, color=c_clean, linestyle="--", alpha=0.5, label="Clean Baseline")
    axes[2].plot(x, drift_series, color=c_fault, linewidth=2.0, label="Drift Injected (+9°C over 24h)")
    axes[2].set_title("3. Calibration Drift (Gradual Sensor Degradation / Thermal Bias)", fontsize=11, fontweight="bold", color=c_text, loc="left")
    axes[2].set_ylabel("Temp (°C)", fontsize=9, color=c_muted)
    axes[2].grid(True, linestyle=":", color=c_grid)
    axes[2].legend(loc="upper right", fontsize=8)

    # Panel 4: Dropout (Missing Telemetry)
    axes[3].plot(x, clean_series, color=c_clean, linestyle="--", alpha=0.5, label="Clean Baseline")
    # For dropout plot, plot valid points with gap where null
    axes[3].plot(x, dropout_series, color=c_fault, linewidth=2.0, marker="x", markersize=4, label="Dropout (Telemetry Gap)")
    axes[3].set_title("4. Telemetry Dropout (Missing Timestamps / Power Failure — Not Zero-Filled)", fontsize=11, fontweight="bold", color=c_text, loc="left")
    axes[3].set_xlabel("Observation Timestep (Hourly Interval)", fontsize=9, color=c_text)
    axes[3].set_ylabel("Temp (°C)", fontsize=9, color=c_muted)
    axes[3].grid(True, linestyle=":", color=c_grid)
    axes[3].legend(loc="upper right", fontsize=8)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.suptitle(title, fontsize=13, fontweight="bold", y=0.98, color=c_text)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close(fig)
    print(f"Saved fault injection verification plot to: {output_path}")
    return output_path


def generate_labeled_benchmark_dataset(
    clean_df: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate complete labeled dataset with all 4 fault types across multiple stations.
    Used for training and evaluating F6 (ML scorer) and F8 (classifier).
    """
    rng = np.random.default_rng(seed)
    df = clean_df.copy()
    df["is_anomalous"] = False
    df["fault_type"] = "valid"
    df["fault_variable"] = None

    stations = df["station_id"].unique()
    if len(stations) == 0:
        return df

    # Station 1: Injected Flatline
    st1 = stations[0]
    df = inject_flatline(df, variable="temperature", station_id=st1, start_idx=10, duration=8)

    # Station 2: Injected Spike (positive)
    if len(stations) > 1:
        st2 = stations[1]
        df = inject_spike(df, variable="temperature", station_id=st2, idx=16, magnitude=18.0)

    # Station 3: Injected Spike (negative / drop spike)
    if len(stations) > 2:
        st3 = stations[2]
        df = inject_spike(df, variable="humidity", station_id=st3, idx=20, magnitude=-40.0)

    # Station 4: Injected Drift
    if len(stations) > 3:
        st4 = stations[3]
        df = inject_drift(df, variable="temperature", station_id=st4, start_idx=12, duration=24, total_drift=10.0)

    # Station 5: Injected Dropout
    if len(stations) > 4:
        st5 = stations[4]
        df = inject_dropout(df, station_id=st5, start_idx=18, duration=6, as_missing_rows=False)

    return df


def main():
    parser = argparse.ArgumentParser(description="AeroSentinel Sensor Fault Injector")
    parser.add_argument("--demo-plot", action="store_true", help="Generate 4-panel visual verification plot")
    parser.add_argument("--output", type=str, default="reports/injected_faults_spotcheck.png", help="Plot image output path")
    args = parser.parse_args()

    # Generate synthetic 48h clean baseline
    from ingestion.simulator import generate_synthetic_weather_stream
    from storage.models import Station

    dummy_station = Station(station_code="NCR001", name="Delhi (Safdarjung)", latitude=28.58, longitude=77.20, elevation_m=216.0)
    now = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    clean_df = generate_synthetic_weather_stream([dummy_station], now, hours=48)

    flatline_df = inject_flatline(clean_df, variable="temperature", station_id="NCR001", start_idx=12, duration=8)
    spike_df = inject_spike(clean_df, variable="temperature", station_id="NCR001", idx=22, magnitude=16.0)
    drift_df = inject_drift(clean_df, variable="temperature", station_id="NCR001", start_idx=10, duration=24, total_drift=9.0)
    dropout_df = inject_dropout(clean_df, station_id="NCR001", start_idx=16, duration=6, as_missing_rows=False)

    out_file = Path(args.output)
    plot_injected_faults(
        clean_series=clean_df["temperature"],
        flatline_series=flatline_df["temperature"],
        spike_series=spike_df["temperature"],
        drift_series=drift_df["temperature"],
        dropout_series=dropout_df["temperature"],
        output_path=out_file,
    )
    print("Fault injection verification complete.")


if __name__ == "__main__":
    main()
