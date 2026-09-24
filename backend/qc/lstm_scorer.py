"""
lstm_scorer.py — Deep Learning Time-Series LSTM-Autoencoder Scorer (F9)
Feature: F9 — LSTM-Autoencoder upgrade (Phase 5 Stretch Goal)

1. PyTorch sequence-to-sequence LSTM Autoencoder (Encoder -> Latent -> Decoder).
2. Operates on sliding temporal sequence windows (W=12 steps / 3 hours).
3. Learns smooth temporal manifold of clean diurnal meteorological cycles.
4. Detects anomalies via Mean Squared Reconstruction Error (MSE).
5. Provides side-by-side benchmark evaluation demonstrating drift & flatline recall improvements over Isolation Forest.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session
from sqlalchemy import desc
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from storage.models import Station, RawReading, QCResult, QCVerdict, ModelRegistry
from qc.ml_scorer import ARTIFACTS_DIR, compute_features_for_series, score_reading, ModelBundle

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. PyTorch LSTM Autoencoder Architecture
# ---------------------------------------------------------------------------

class LSTMAutoencoder(nn.Module):
    """
    Sequence-to-Sequence LSTM Autoencoder for temporal anomaly detection.
    Compresses sequential sensor windows into a latent bottleneck, then
    reconstructs the sequence. High reconstruction error indicates sequence deformation.
    """

    def __init__(self, input_dim: int = 1, hidden_dim: int = 24, num_layers: int = 1):
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # Encoder: compresses (B, seq_len, input_dim) -> hidden state (B, hidden_dim)
        self.encoder = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
        )

        # Decoder: reconstructs (B, seq_len, hidden_dim) -> (B, seq_len, input_dim)
        self.decoder = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
        )
        self.output_layer = nn.Linear(hidden_dim, input_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, _ = x.shape

        # 1. Encode
        _, (h_n, _) = self.encoder(x)
        # Latent vector from last layer: (B, hidden_dim)
        latent = h_n[-1]

        # 2. Repeat latent representation across all sequence timesteps for decoder
        dec_input = latent.unsqueeze(1).repeat(1, seq_len, 1)

        # 3. Decode
        dec_output, _ = self.decoder(dec_input)
        reconstruction = self.output_layer(dec_output)
        return reconstruction


# ---------------------------------------------------------------------------
# 2. LSTM Model Bundle
# ---------------------------------------------------------------------------

@dataclass
class LSTMModelBundle:
    """Encapsulates a trained LSTM-Autoencoder, scaler, and calibrated threshold."""
    model: LSTMAutoencoder
    scaler: StandardScaler
    variable: str
    station_code: str
    version: str
    seq_length: int
    threshold: float
    mean_train_error: float
    trained_at: str

    def save(self, file_path: Path) -> Path:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "model_config": {
                "input_dim": self.model.input_dim,
                "hidden_dim": self.model.hidden_dim,
                "num_layers": self.model.num_layers,
            },
            "scaler": self.scaler,
            "variable": self.variable,
            "station_code": self.station_code,
            "version": self.version,
            "seq_length": self.seq_length,
            "threshold": self.threshold,
            "mean_train_error": self.mean_train_error,
            "trained_at": self.trained_at,
        }
        torch.save(checkpoint, file_path)
        return file_path

    @classmethod
    def load(cls, file_path: Path) -> "LSTMModelBundle":
        checkpoint = torch.load(file_path, weights_only=False, map_location="cpu")
        cfg = checkpoint["model_config"]
        model = LSTMAutoencoder(
            input_dim=cfg["input_dim"],
            hidden_dim=cfg["hidden_dim"],
            num_layers=cfg["num_layers"],
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        return cls(
            model=model,
            scaler=checkpoint["scaler"],
            variable=checkpoint["variable"],
            station_code=checkpoint["station_code"],
            version=checkpoint["version"],
            seq_length=checkpoint["seq_length"],
            threshold=checkpoint["threshold"],
            mean_train_error=checkpoint["mean_train_error"],
            trained_at=checkpoint["trained_at"],
        )


# Global in-memory cache for fast inference
_LSTM_MODEL_CACHE: Dict[str, LSTMModelBundle] = {}


# ---------------------------------------------------------------------------
# 3. Sliding Window & Dataset Utilities
# ---------------------------------------------------------------------------

def create_sliding_windows(values: List[float], seq_length: int = 12) -> np.ndarray:
    """
    Generate sliding temporal sequence windows of shape (N - W + 1, W, 1).
    """
    clean_vals = [float(v) for v in values if v is not None and not math.isnan(v)]
    if len(clean_vals) < seq_length:
        return np.empty((0, seq_length, 1), dtype=np.float32)

    windows = []
    for i in range(len(clean_vals) - seq_length + 1):
        win = clean_vals[i : i + seq_length]
        windows.append(win)

    arr = np.array(windows, dtype=np.float32)
    return np.expand_dims(arr, axis=-1)  # (N, W, 1)


# ---------------------------------------------------------------------------
# 4. Training Engine
# ---------------------------------------------------------------------------

def train_lstm_autoencoder(
    train_df: pd.DataFrame,
    variable: str = "temperature",
    station_code: str = "FLEET",
    version: str = "v1.0.0-lstm",
    seq_length: int = 12,
    hidden_dim: int = 24,
    epochs: int = 30,
    lr: float = 0.005,
    batch_size: int = 32,
    random_seed: int = 42,
) -> LSTMModelBundle:
    """
    Train an LSTM-Autoencoder on clean baseline time-series history.
    Calibrates reconstruction MSE anomaly threshold at 98th percentile of clean training error.
    """
    torch.manual_seed(random_seed)
    np.random.seed(random_seed)

    clean_series = train_df.dropna(subset=[variable]).sort_values("timestamp")
    values = clean_series[variable].tolist()

    if len(values) < seq_length * 3:
        raise ValueError(
            f"Insufficient training samples for LSTM-AE ({len(values)} < {seq_length * 3})"
        )

    # 1. Fit standard scaler on raw sensor values
    scaler = StandardScaler()
    scaled_values = scaler.fit_transform(np.array(values).reshape(-1, 1)).flatten().tolist()

    # 2. Create sequence windows (N, W, 1)
    windows = create_sliding_windows(scaled_values, seq_length=seq_length)
    if len(windows) == 0:
        raise ValueError("No valid sliding windows generated.")

    tensor_data = torch.from_numpy(windows)
    dataset = TensorDataset(tensor_data)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # 3. Initialize Model, Optimizer, Loss
    model = LSTMAutoencoder(input_dim=1, hidden_dim=hidden_dim, num_layers=1)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    model.train()
    for epoch in range(epochs):
        epoch_loss = 0.0
        for (batch_x,) in loader:
            optimizer.zero_grad()
            reconstructed = model(batch_x)
            loss = criterion(reconstructed, batch_x)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(batch_x)

    # 4. Compute empirical reconstruction errors on clean training windows
    model.eval()
    with torch.no_grad():
        recon_train = model(tensor_data)
        # Compute MSE per window
        train_mse = torch.mean((recon_train - tensor_data) ** 2, dim=[1, 2]).numpy()

    mean_err = float(np.mean(train_mse))
    std_err = float(np.std(train_mse))

    # Calibrate decision threshold: 98th percentile of clean reconstruction MSE
    threshold = float(np.percentile(train_mse, 98.0))
    if threshold < mean_err + 2.0 * std_err:
        threshold = mean_err + 2.5 * std_err

    bundle = LSTMModelBundle(
        model=model,
        scaler=scaler,
        variable=variable,
        station_code=station_code,
        version=version,
        seq_length=seq_length,
        threshold=threshold,
        mean_train_error=mean_err,
        trained_at=datetime.now(timezone.utc).isoformat(),
    )
    return bundle


# ---------------------------------------------------------------------------
# 5. Inference / Sequence Scoring
# ---------------------------------------------------------------------------

def score_sequence(
    bundle: LSTMModelBundle,
    current_value: Optional[float],
    prior_values: List[float],
    timestamp: datetime,
) -> Tuple[bool, float, float, Dict[str, Any]]:
    """
    Score a reading and its preceding temporal window against the trained LSTM-Autoencoder.
    Returns:
    - is_anomalous: bool
    - anomaly_score: float in [0.0, 1.0] (higher means larger reconstruction distortion)
    - confidence: float in [0.0, 1.0]
    - details: dict containing MSE, threshold, and reconstruction residuals
    """
    if current_value is None or math.isnan(current_value):
        return False, 0.0, 0.0, {"reason": "missing_or_nan"}

    # Form window: prior_values + current_value
    full_seq = prior_values + [current_value]
    if len(full_seq) < bundle.seq_length:
        # Pad with current value if history is insufficient
        pad_len = bundle.seq_length - len(full_seq)
        full_seq = [full_seq[0]] * pad_len + full_seq
    else:
        full_seq = full_seq[-bundle.seq_length :]

    # Scale window
    scaled = bundle.scaler.transform(np.array(full_seq).reshape(-1, 1)).flatten()
    tensor_input = torch.from_numpy(scaled).float().unsqueeze(0).unsqueeze(-1)  # (1, W, 1)

    bundle.model.eval()
    with torch.no_grad():
        reconstructed = bundle.model(tensor_input)
        mse = float(torch.mean((reconstructed - tensor_input) ** 2).item())

    # Sigmoid scaling for normalized anomaly score [0.0, 1.0]
    # Ratio > 1.0 means mse exceeds threshold -> anomalous (score > 0.5)
    ratio = mse / (bundle.threshold + 1e-6)
    anomaly_score = 1.0 / (1.0 + math.exp(-5.0 * (ratio - 1.0)))
    anomaly_score = max(0.0, min(1.0, anomaly_score))

    is_anomalous = bool(mse > bundle.threshold)
    confidence = round(float(min(0.99, max(0.50, 0.50 + 0.49 * min(1.0, ratio)))), 2)

    details = {
        "model_type": "lstm_autoencoder",
        "model_version": bundle.version,
        "reconstruction_mse": round(mse, 5),
        "threshold": round(bundle.threshold, 5),
        "normalized_anomaly_score": round(anomaly_score, 4),
        "sequence_length": bundle.seq_length,
        "current_value": round(float(current_value), 2),
    }

    return is_anomalous, anomaly_score, confidence, details


# ---------------------------------------------------------------------------
# 6. Side-by-Side Benchmark Evaluation (Phase 5 Exit Criterion)
# ---------------------------------------------------------------------------

def evaluate_side_by_side(
    lstm_bundle: LSTMModelBundle,
    iforest_bundle: ModelBundle,
    benchmark_df: pd.DataFrame,
    variable: str = "temperature",
    output_report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run side-by-side inference of LSTM-Autoencoder vs IsolationForest baseline
    across the multi-station labeled benchmark dataset from F5.
    Demonstrates specifically whether LSTM-AE improves recall on sensor calibration drift.
    """
    df = benchmark_df.copy().sort_values("timestamp")
    stations = df["station_id"].unique()

    y_true: List[bool] = []
    fault_types: List[str] = []
    y_pred_iforest: List[bool] = []
    y_pred_lstm: List[bool] = []

    for st in stations:
        st_df = df[df["station_id"] == st].sort_values("timestamp")
        prior_vals: List[float] = []

        for _, row in st_df.iterrows():
            val = row.get(variable)
            ts = row["timestamp"]
            is_gt_anomaly = bool(row.get("is_anomalous", False))
            ftype = str(row.get("fault_type", "valid"))
            fault_var = row.get("fault_variable")

            # Only evaluate anomalies targeting this specific variable or valid rows
            if is_gt_anomaly and fault_var and fault_var != variable:
                continue

            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                # Score with IsolationForest
                is_anom_if, _, _, _ = score_reading(iforest_bundle, val, prior_vals, ts)
                # Score with LSTM-AE
                is_anom_lstm, _, _, _ = score_sequence(lstm_bundle, val, prior_vals, ts)

                y_true.append(is_gt_anomaly)
                fault_types.append(ftype)
                y_pred_iforest.append(is_anom_if)
                y_pred_lstm.append(is_anom_lstm)

                prior_vals.append(val)
                if len(prior_vals) > 20:
                    prior_vals.pop(0)

    # Compute metrics per fault type
    unique_faults = sorted(list(set(fault_types)))
    comparison_by_type = {}

    for ft in unique_faults:
        indices = [i for i, f in enumerate(fault_types) if f == ft]
        if not indices:
            continue

        gt_count = sum(1 for i in indices if y_true[i])
        detected_if = sum(1 for i in indices if y_pred_iforest[i] and y_true[i])
        detected_lstm = sum(1 for i in indices if y_pred_lstm[i] and y_true[i])

        recall_if = round(detected_if / gt_count, 4) if gt_count > 0 else 1.0
        recall_lstm = round(detected_lstm / gt_count, 4) if gt_count > 0 else 1.0

        comparison_by_type[ft] = {
            "ground_truth_count": gt_count,
            "isolation_forest_recall": recall_if,
            "lstm_ae_recall": recall_lstm,
            "improvement_pct": round((recall_lstm - recall_if) * 100.0, 1),
        }

    # Overall Metrics
    def calc_stats(y_p):
        tp = sum(1 for i in range(len(y_true)) if y_true[i] and y_p[i])
        fp = sum(1 for i in range(len(y_true)) if not y_true[i] and y_p[i])
        fn = sum(1 for i in range(len(y_true)) if y_true[i] and not y_p[i])
        p = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        r = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round(2 * p * r / (p + r), 4) if (p + r) > 0 else 0.0
        return {"precision": p, "recall": r, "f1": f1}

    if_stats = calc_stats(y_pred_iforest)
    lstm_stats = calc_stats(y_pred_lstm)

    report = {
        "variable": variable,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total_eval_samples": len(y_true),
        "overall": {
            "isolation_forest": if_stats,
            "lstm_autoencoder": lstm_stats,
        },
        "per_fault_type_comparison": comparison_by_type,
        "phase_5_exit_criterion_met": bool(
            comparison_by_type.get("drift", {}).get("lstm_ae_recall", 0.0)
            > comparison_by_type.get("drift", {}).get("isolation_forest_recall", 0.0)
        ),
    }

    if output_report_path:
        output_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_report_path, "w") as f:
            json.dump(report, f, indent=2)

    return report


# ---------------------------------------------------------------------------
# 7. Model Registration & Cache Management
# ---------------------------------------------------------------------------

def register_lstm_bundle(
    db: Session,
    bundle: LSTMModelBundle,
    metrics: Dict[str, Any],
    artifact_path: str,
) -> ModelRegistry:
    """
    Register LSTM-Autoencoder bundle in model_registry table.
    Deactivates any existing active models for this variable and activates this new one.
    """
    db.query(ModelRegistry).filter(
        ModelRegistry.variable == bundle.variable,
        ModelRegistry.is_active == True,
    ).update({"is_active": False})

    reg = ModelRegistry(
        model_type="lstm_autoencoder",
        variable=bundle.variable,
        version=bundle.version,
        trained_at=datetime.now(timezone.utc),
        training_data_range=f"Station {bundle.station_code}",
        metrics=metrics,
        artifact_path=artifact_path,
        is_active=True,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    _LSTM_MODEL_CACHE[bundle.variable] = bundle
    return reg


def get_active_lstm_bundle(variable: str, db: Optional[Session] = None) -> Optional[LSTMModelBundle]:
    """Retrieve active LSTMModelBundle from memory cache, database registry, or disk."""
    if variable in _LSTM_MODEL_CACHE:
        return _LSTM_MODEL_CACHE[variable]

    if db:
        reg = (
            db.query(ModelRegistry)
            .filter(
                ModelRegistry.variable == variable,
                ModelRegistry.model_type == "lstm_autoencoder",
                ModelRegistry.is_active == True,
            )
            .first()
        )
        if reg and reg.artifact_path and Path(reg.artifact_path).exists():
            bundle = LSTMModelBundle.load(Path(reg.artifact_path))
            _LSTM_MODEL_CACHE[variable] = bundle
            return bundle

    artifact_file = ARTIFACTS_DIR / f"{variable}_lstm_ae.pt"
    if artifact_file.exists():
        bundle = LSTMModelBundle.load(artifact_file)
        _LSTM_MODEL_CACHE[variable] = bundle
        return bundle

    return None
