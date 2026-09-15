"""Metrics aggregation and evaluation."""
from __future__ import annotations

from typing import Dict, Any
import pandas as pd
from sklearn.metrics import f1_score


def compute_summary_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute overall accuracy, F1, and distributions."""
    has_labels = "true_damage_class" in df.columns and "true_stress_class" in df.columns

    damage_acc = None
    stress_acc = None
    state_acc = None
    macro_f1 = None

    if has_labels:
        damage_acc = float(df["damage_correct"].mean())
        stress_acc = float(df["stress_correct"].mean())
        state_acc = float(df["state_correct"].mean())
        macro_f1 = float(
            f1_score(
                df["true_state_class"],
                df["pred_state_class"],
                average="macro",
                zero_division=0,
            )
        )

    mean_conf = float(df["state_confidence"].mean()) if "state_confidence" in df.columns else 0.0

    damage_counts = df["pred_damage_level"].value_counts().to_dict()
    stress_counts = df["pred_stress_mpa"].value_counts().to_dict()

    return {
        "num_windows": int(len(df)),
        "has_ground_truth": has_labels,
        "damage_accuracy": damage_acc,
        "stress_accuracy": stress_acc,
        "state_accuracy": state_acc,
        "macro_f1": macro_f1,
        "mean_confidence": mean_conf,
        "damage_distribution": {str(k): int(v) for k, v in damage_counts.items()},
        "stress_distribution": {str(k): int(v) for k, v in stress_counts.items()},
    }

