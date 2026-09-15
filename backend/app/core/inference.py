"""Model loading and batch inference engine."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple, Dict, Any

import numpy as np
import pandas as pd
import torch

from app.config import (
    DEVICE,
    DEFAULT_MODEL_PATH,
    DAMAGE_CLASS_TO_LEVEL,
    STRESS_CLASS_TO_MPA,
    STATE_TO_LABEL,
)
from app.core.model import FullModelStandard


def scale_array(values: np.ndarray, mean: Any, std: Any) -> np.ndarray:
    """Normalize array using mean/std, broadcasting along trailing dimensions."""
    mean_arr = np.asarray(mean, dtype=np.float32)
    std_arr = np.asarray(std, dtype=np.float32)
    std_arr[std_arr < 1e-8] = 1.0
    return ((values - mean_arr) / std_arr).astype(np.float32)


def load_model(
    model_path: Path = DEFAULT_MODEL_PATH,
    device: torch.device = DEVICE,
) -> Tuple[FullModelStandard, dict]:
    """Load model weights and checkpoint dictionary."""
    if not model_path.exists():
        raise FileNotFoundError(f"找不到模型权重文件: {model_path}")

    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    model = FullModelStandard()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    model.to(device)
    return model, checkpoint


def run_model_inference(
    model: FullModelStandard,
    checkpoint: dict,
    seq_arr: np.ndarray,
    phys_arr: np.ndarray,
    meta_df: pd.DataFrame,
    device: torch.device = DEVICE,
    batch_size: int = 512,
) -> pd.DataFrame:
    """Run batch forward pass on normalized windows."""
    seq_mean = checkpoint["seq_scaler"]["mean"]
    seq_std = checkpoint["seq_scaler"]["std"]
    phys_mean = checkpoint["phys_scaler"]["mean"]
    phys_std = checkpoint["phys_scaler"]["std"]

    seq_scaled = scale_array(seq_arr, seq_mean, seq_std)
    phys_scaled = scale_array(phys_arr, phys_mean, phys_std)

    preds_damage = []
    preds_stress = []
    preds_state = []
    state_probs = []

    total_samples = len(seq_scaled)
    with torch.no_grad():
        for start in range(0, total_samples, batch_size):
            end = min(start + batch_size, total_samples)
            seq_batch = torch.from_numpy(seq_scaled[start:end]).to(device)
            phys_batch = torch.from_numpy(phys_scaled[start:end]).to(device)

            out = model(seq_batch, phys_batch)

            preds_damage.append(torch.argmax(out["damage"], dim=1).cpu().numpy())
            preds_stress.append(torch.argmax(out["stress"], dim=1).cpu().numpy())
            preds_state.append(torch.argmax(out["state"], dim=1).cpu().numpy())

            probs = torch.softmax(out["state"], dim=1).cpu().numpy()
            state_probs.append(probs)

    result = meta_df.copy()
    result["pred_damage_class"] = np.concatenate(preds_damage).astype(int)
    result["pred_stress_class"] = np.concatenate(preds_stress).astype(int)
    result["pred_state_class"] = np.concatenate(preds_state).astype(int)

    all_probs = np.vstack(state_probs)
    result["state_confidence"] = all_probs.max(axis=1).astype(float)

    # Map to domain values
    result["pred_damage_level"] = result["pred_damage_class"].map(DAMAGE_CLASS_TO_LEVEL).astype(int)
    result["pred_stress_mpa"] = result["pred_stress_class"].map(STRESS_CLASS_TO_MPA).astype(int)
    result["pred_state_label"] = result["pred_state_class"].map(STATE_TO_LABEL)

    # Evaluate accuracy if true labels present
    if "true_damage_class" in result.columns and "true_stress_class" in result.columns:
        result["damage_correct"] = result["pred_damage_class"] == result["true_damage_class"]
        result["stress_correct"] = result["pred_stress_class"] == result["true_stress_class"]
        result["state_correct"] = result["pred_state_class"] == result["true_state_class"]

    return result

