"""Data validation and multi-scale feature preprocessing."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple, Dict, Any, List

import numpy as np
import pandas as pd

from app.config import (
    MIN_WINDOW,
    SEQ_WINDOW,
    WINDOW_SIZES,
    MULTISCALE_FEATURE_NAMES,
)

CRITICAL_COLUMNS = ["depth_cm", "torque_nm", "thrust_kn"]
LABEL_COLUMNS = [
    "true_damage_level",
    "true_damage_class",
    "true_stress_mpa",
    "true_stress_class",
    "true_state_class",
    "segment_index",
    "true_state_label",
]


def validate_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Validate raw drilling dataframe structure and values."""
    missing = [col for col in CRITICAL_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"CSV 缺少必需传感器字段: {missing}")

    if len(df) < MIN_WINDOW:
        raise ValueError(f"样本行数 ({len(df)}) 小于多尺度滑动窗口最小长度 ({MIN_WINDOW})")

    # Check for non-numeric or missing in critical columns
    for col in CRITICAL_COLUMNS:
        if not pd.api.types.is_numeric_dtype(df[col]):
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception as e:
                raise ValueError(f"字段 {col} 无法转换为数值类型: {e}")
        if df[col].isna().any():
            df[col] = df[col].ffill().bfill().fillna(0.0)

    has_labels = all(col in df.columns for col in ["true_damage_level", "true_stress_mpa"])
    return {
        "total_rows": len(df),
        "has_labels": has_labels,
        "depth_range": [float(df["depth_cm"].min()), float(df["depth_cm"].max())],
        "torque_range": [float(df["torque_nm"].min()), float(df["torque_nm"].max())],
        "thrust_range": [float(df["thrust_kn"].min()), float(df["thrust_kn"].max())],
    }


def compute_multiscale_matrix(values: np.ndarray) -> np.ndarray:
    """
    Compute 4-scale (25, 50, 100, 200) x 20 features = 80 physical features.
    Matches original vtest3_utils implementation exactly.
    """
    frame = pd.DataFrame(values, columns=["depth", "torque", "thrust"])
    blocks = []

    for size in WINDOW_SIZES:
        roll = frame.rolling(window=size, min_periods=size)
        torque_mean = roll["torque"].mean()
        thrust_mean = roll["thrust"].mean()
        torque_min = roll["torque"].min()
        torque_max = roll["torque"].max()
        thrust_min = roll["thrust"].min()
        thrust_max = roll["thrust"].max()

        sum_depth = roll["depth"].sum()
        sum_depth2 = (frame["depth"] * frame["depth"]).rolling(window=size, min_periods=size).sum()
        denom = size * sum_depth2 - sum_depth * sum_depth
        denom_clean = denom.replace(0.0, np.nan)

        sum_torque = roll["torque"].sum()
        sum_depth_torque = (frame["depth"] * frame["torque"]).rolling(window=size, min_periods=size).sum()
        torque_slope = (size * sum_depth_torque - sum_depth * sum_torque) / denom_clean

        sum_thrust = roll["thrust"].sum()
        sum_depth_thrust = (frame["depth"] * frame["thrust"]).rolling(window=size, min_periods=size).sum()
        thrust_slope = (size * sum_depth_thrust - sum_depth * sum_thrust) / denom_clean

        corr = roll["torque"].corr(frame["thrust"]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        ratio = (torque_mean / thrust_mean).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        blocks.append(
            pd.DataFrame(
                {
                    f"w{size}_torque_mean": torque_mean,
                    f"w{size}_torque_std": roll["torque"].std(ddof=0),
                    f"w{size}_torque_min": torque_min,
                    f"w{size}_torque_max": torque_max,
                    f"w{size}_torque_ptp": torque_max - torque_min,
                    f"w{size}_torque_q25": roll["torque"].quantile(0.25),
                    f"w{size}_torque_q75": roll["torque"].quantile(0.75),
                    f"w{size}_torque_slope": torque_slope.replace([np.inf, -np.inf], np.nan).fillna(0.0),
                    f"w{size}_thrust_mean": thrust_mean,
                    f"w{size}_thrust_std": roll["thrust"].std(ddof=0),
                    f"w{size}_thrust_min": thrust_min,
                    f"w{size}_thrust_max": thrust_max,
                    f"w{size}_thrust_ptp": thrust_max - thrust_min,
                    f"w{size}_thrust_q25": roll["thrust"].quantile(0.25),
                    f"w{size}_thrust_q75": roll["thrust"].quantile(0.75),
                    f"w{size}_thrust_slope": thrust_slope.replace([np.inf, -np.inf], np.nan).fillna(0.0),
                    f"w{size}_torque_thrust_corr": corr,
                    f"w{size}_torque_thrust_ratio": ratio,
                    f"w{size}_depth_start": frame["depth"].shift(size - 1),
                    f"w{size}_depth_end": frame["depth"],
                }
            )
        )

    features = pd.concat(blocks, axis=1)
    # Start at MIN_WINDOW - 1 (index 199)
    return features.loc[MIN_WINDOW - 1 :, MULTISCALE_FEATURE_NAMES].to_numpy(dtype=np.float32)


def prepare_sliding_windows(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """
    Construct sliding sequence windows and physical feature matrix.
    Returns:
      seq_arr: (N_windows, 100, 3)
      phys_arr: (N_windows, 80)
      meta_df: DataFrame with aligned metadata for each window end point.
    """
    validate_dataframe(df)
    values = df[["depth_cm", "torque_nm", "thrust_kn"]].to_numpy(dtype=np.float32)
    phys_matrix = compute_multiscale_matrix(values)

    seq_rows = []
    meta_rows = []
    num_rows = len(df)

    has_labels = all(col in df.columns for col in ["true_damage_level", "true_stress_mpa"])

    for end in range(MIN_WINDOW - 1, num_rows):
        current = df.iloc[end]
        seq_rows.append(values[end - SEQ_WINDOW + 1 : end + 1])
        meta_dict = {
            "window_index": end - (MIN_WINDOW - 1),
            "sample_index": int(current.get("sample_index", end)),
            "depth_cm": float(current["depth_cm"]),
            "torque_nm": float(current["torque_nm"]),
            "thrust_kn": float(current["thrust_kn"]),
            "cumulative_depth_cm": float(current.get("cumulative_depth_cm", current["depth_cm"])),
        }
        if has_labels:
            meta_dict.update({
                "true_damage_level": int(current.get("true_damage_level", 0)),
                "true_damage_class": int(current.get("true_damage_class", 0)),
                "true_stress_mpa": int(current.get("true_stress_mpa", 0)),
                "true_stress_class": int(current.get("true_stress_class", 0)),
                "true_state_class": int(current.get("true_state_class", 0)),
                "true_state_label": str(current.get("true_state_label", "")),
                "segment_index": int(current.get("segment_index", 0)),
            })
        meta_rows.append(meta_dict)

    seq_arr = np.stack(seq_rows).astype(np.float32)
    phys_arr = phys_matrix.astype(np.float32)
    meta_df = pd.DataFrame(meta_rows)

    return seq_arr, phys_arr, meta_df

