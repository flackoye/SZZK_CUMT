"""Adapter to shape inference results into frontend-compatible payload."""
from __future__ import annotations

from typing import Dict, Any, List
import copy
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import numpy as np

logger = logging.getLogger("szic.result_adapter")

# Base directory for template lookup
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_SPATIAL_TEMPLATE_PATH = _BASE_DIR.parent / "qianduan" / "public" / "data" / "roadway_spatial_v4.json"
_cached_spatial_template: Optional[Dict[str, Any]] = None


def _get_spatial_template() -> Dict[str, Any]:
    global _cached_spatial_template
    if _cached_spatial_template is not None:
        return copy.deepcopy(_cached_spatial_template)

    if _SPATIAL_TEMPLATE_PATH.exists():
        try:
            data = json.loads(_SPATIAL_TEMPLATE_PATH.read_text(encoding="utf-8"))
            _cached_spatial_template = data
            return copy.deepcopy(data)
        except Exception as e:
            logger.warning(f"Failed to read spatial template {_SPATIAL_TEMPLATE_PATH}: {e}")

    # Fallback minimal template if file not accessible
    return {
        "meta": {
            "title": "三断面十一孔巷道空间反演场",
            "geometry": "arched roadway extruded along longitudinal X axis",
            "groupCount": 3,
            "boreholesPerGroup": 11,
            "depthRangeCm": [0.0, 125.0],
            "depthStepCm": 2.5,
            "model": "V3-Full",
        },
        "groups": [
            {"id": "A", "label": "A 组", "longitudinalM": -8.0, "boreholeCount": 11, "boreholes": []},
            {"id": "B", "label": "B 组", "longitudinalM": 0.0, "boreholeCount": 11, "boreholes": []},
            {"id": "C", "label": "C 组", "longitudinalM": 8.0, "boreholeCount": 11, "boreholes": []},
        ],
    }


def _resample_depth_series(df_pred: pd.DataFrame, depth_steps: np.ndarray) -> List[Dict[str, Any]]:
    """Resample predictions into exact 50 standard depth intervals (2.5 to 125 cm)."""
    samples = []
    has_truth = "true_damage_level" in df_pred.columns and "true_stress_mpa" in df_pred.columns

    depths = df_pred["depth_cm"].to_numpy()
    pred_stresses = df_pred["pred_stress_mpa"].to_numpy()
    pred_damages = df_pred["pred_damage_level"].to_numpy()
    confidences = df_pred["state_confidence"].to_numpy() if "state_confidence" in df_pred.columns else np.ones(len(df_pred)) * 0.9

    true_stresses = df_pred["true_stress_mpa"].to_numpy() if has_truth else None
    true_damages = df_pred["true_damage_level"].to_numpy() if has_truth else None

    for d in depth_steps:
        # Find closest index
        diff = np.abs(depths - d)
        idx = int(np.argmin(diff))

        item: Dict[str, Any] = {
            "depthCm": round(float(d), 1),
            "stressMpa": round(float(pred_stresses[idx]), 1),
            "damagePct": round(float(pred_damages[idx]), 1),
            "confidence": round(float(confidences[idx]), 4),
        }
        if has_truth and true_stresses is not None and true_damages is not None:
            item["trueStressMpa"] = round(float(true_stresses[idx]), 1)
            item["trueDamagePct"] = round(float(true_damages[idx]), 1)
        else:
            item["trueStressMpa"] = None
            item["trueDamagePct"] = None

        samples.append(item)

    return samples


def _build_spatial_roadway(
    run_id: str,
    file_name: str,
    df_pred: pd.DataFrame,
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Build dynamic 3D spatial roadway payload driven by real inference results."""
    spatial = _get_spatial_template()
    depth_steps = np.arange(2.5, 127.5, 2.5)  # 50 points: 2.5, 5.0, ..., 125.0 cm
    resampled_samples = _resample_depth_series(df_pred, depth_steps)

    # Determine borehole index from filename (defaults to BH-03 / S20)
    file_lower = file_name.lower()
    borehole_map = {
        "s00_1": 10,
        "s10_1": 9,
        "s20_1": 8,
        "s30_1": 7,
        "s40_1": 6,
        "s99": 5,
        "s40": 4,
        "s30": 3,
        "s20": 2,
        "s10": 1,
        "s00": 0,
    }
    target_surface_idx = 2  # default BH-03
    for k, idx in borehole_map.items():
        if k in file_lower:
            target_surface_idx = idx
            break

    target_hole_id_suffix = f"{target_surface_idx + 1:02d}"

    spatial["meta"]["runId"] = run_id
    spatial["meta"]["sourceFile"] = file_name
    spatial["meta"]["model"] = "V3-Full"
    spatial["meta"]["activeSurfaceIndex"] = target_surface_idx
    spatial["meta"]["activeBoreholeId"] = f"BH-{target_hole_id_suffix}"
    spatial["meta"]["title"] = f"任务 {run_id} 空间反演场 (驱动自 {file_name})"

    # Update groups
    for group in spatial.get("groups", []):
        group["model"] = "V3-Full"
        group["runId"] = run_id
        if metrics.get("damage_accuracy") is not None:
            group["metrics"] = {
                "damageAccuracy": round(metrics["damage_accuracy"], 4),
                "stressAccuracy": round(metrics["stress_accuracy"], 4),
                "stateMacroF1": round(metrics["macro_f1"], 4),
                "meanConfidence": round(metrics.get("mean_confidence", 0.9), 4),
            }
        for hole in group.get("boreholes", []):
            hole_idx = hole.get("surfaceIndex")
            if hole_idx == target_surface_idx:
                hole["samples"] = copy.deepcopy(resampled_samples)
                hole["sourceFile"] = file_name
                hole["runId"] = run_id
                hole["isCurrentRun"] = True
            else:
                hole["isCurrentRun"] = False

    return spatial


def adapt_batch_to_frontend_payload(
    run_id: str,
    file_results: List[Dict[str, Any]],
    work_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Convert batch of raw dataframes and predictions into Vue/Pinia friendly structure."""
    if not file_results:
        raise ValueError("file_results cannot be empty")

    depth_steps = np.arange(2.5, 127.5, 2.5)  # 50 points: 2.5, 5.0, ..., 125.0 cm

    # 1. Process each file: KPIs, downsampled series, resampled 3D samples
    for f in file_results:
        df_raw = f["df_raw"]
        df_pred = f["df_pred"]

        torque_mean = float(df_raw["torque_nm"].mean())
        torque_max = float(df_raw["torque_nm"].max())
        thrust_mean = float(df_raw["thrust_kn"].mean())
        thrust_max = float(df_raw["thrust_kn"].max())
        depth_max = float(df_raw["depth_cm"].max())

        f["kpis"] = {
            "torque_mean": round(torque_mean, 1),
            "torque_max": round(torque_max, 1),
            "thrust_mean": round(thrust_mean, 2),
            "thrust_max": round(thrust_max, 2),
            "depth_max": round(depth_max, 1),
        }

        # Downsample series for charts (up to 600 points per borehole)
        step = max(1, len(df_pred) // 600)
        sampled = df_pred.iloc[::step].copy()
        series_list: List[Dict[str, Any]] = []
        for _, row in sampled.iterrows():
            item = {
                "sample": int(row.get("sample_index", row.get("window_index", 0))),
                "depth": round(float(row["depth_cm"]), 2),
                "torque": round(float(row["torque_nm"]), 2),
                "thrust": round(float(row["thrust_kn"]), 3),
                "damage": int(row["pred_damage_level"]),
                "stress": int(row["pred_stress_mpa"]),
                "state": str(row["pred_state_label"]),
                "confidence": round(float(row["state_confidence"]), 3),
            }
            if "true_damage_level" in row:
                item["true_damage"] = int(row["true_damage_level"])
            if "true_stress_mpa" in row:
                item["true_stress"] = int(row["true_stress_mpa"])
            series_list.append(item)
        f["series"] = series_list
        f["resampled_samples"] = _resample_depth_series(df_pred, depth_steps)

    # 2. Compute overall batch metrics
    has_truth = any(f["metrics"].get("has_ground_truth", False) for f in file_results)
    if has_truth:
        valid_damage = [f["metrics"]["damage_accuracy"] for f in file_results if f["metrics"].get("damage_accuracy") is not None]
        valid_stress = [f["metrics"]["stress_accuracy"] for f in file_results if f["metrics"].get("stress_accuracy") is not None]
        valid_f1 = [f["metrics"]["macro_f1"] for f in file_results if f["metrics"].get("macro_f1") is not None]
        damage_acc = round(float(np.mean(valid_damage)), 4) if valid_damage else None
        stress_acc = round(float(np.mean(valid_stress)), 4) if valid_stress else None
        macro_f1 = round(float(np.mean(valid_f1)), 4) if valid_f1 else None
    else:
        damage_acc = None
        stress_acc = None
        macro_f1 = None

    valid_conf = [f["metrics"]["mean_confidence"] for f in file_results if f["metrics"].get("mean_confidence") is not None]
    confidence = round(float(np.mean(valid_conf)), 3) if valid_conf else 0.9

    model_info = {
        "id": "v3-full",
        "name": "PF-CL-MTIM",
        "name_en": "PF-CL-MTIM",
        "type": "物理融合深度学习 (V3-Full)",
        "features": "序列窗口 + 80维物理统计特征",
        "damage_accuracy": damage_acc,
        "stress_accuracy": stress_acc,
        "macro_f1": macro_f1,
        "confidence": confidence,
        "has_ground_truth": has_truth,
        "batch_size": len(file_results),
    }

    # 3. Build dynamic 3D spatial roadway for all boreholes
    spatial = _get_spatial_template()
    surface_to_file = {f["surface_index"]: f for f in file_results}

    # Default active borehole is BH-03 (surfaceIndex 2) if present, else first
    active_idx = 2 if 2 in surface_to_file else file_results[0]["surface_index"]
    active_file = surface_to_file.get(active_idx, file_results[0])
    active_hole_id = active_file.get("borehole_id", f"BH-{active_idx + 1:02d}")

    spatial["meta"]["runId"] = run_id
    spatial["meta"]["model"] = "V3-Full"
    spatial["meta"]["batchSize"] = len(file_results)
    spatial["meta"]["activeSurfaceIndex"] = active_idx
    spatial["meta"]["activeBoreholeId"] = active_hole_id
    spatial["meta"]["title"] = f"任务 {run_id} 全断面空间反演场 (驱动自 {len(file_results)} 个实测钻孔)"

    for group in spatial.get("groups", []):
        group["model"] = "V3-Full"
        group["runId"] = run_id
        # Update metrics for measured section B (and other sections)
        if damage_acc is not None:
            group["metrics"] = {
                "damageAccuracy": damage_acc,
                "stressAccuracy": stress_acc,
                "stateMacroF1": macro_f1,
                "meanConfidence": confidence,
            }
        for hole in group.get("boreholes", []):
            h_idx = hole.get("surfaceIndex")
            if h_idx in surface_to_file:
                target_f = surface_to_file[h_idx]
                hole["samples"] = copy.deepcopy(target_f["resampled_samples"])
                hole["sourceFile"] = target_f["file_name"]
                hole["runId"] = run_id
                hole["isCurrentRun"] = True
                hole["boreholeId"] = target_f.get("borehole_id", f"BH-{h_idx + 1:02d}")
            else:
                hole["isCurrentRun"] = False

    # 4. Format files summary for API response
    files_summary = []
    for f in file_results:
        files_summary.append({
            "file_name": f["file_name"],
            "order_index": f.get("order_index", 0),
            "borehole_id": f.get("borehole_id", "BH-01"),
            "surfaceIndex": f.get("surface_index", 0),
            "row_count": len(f["df_raw"]),
            "window_count": len(f["df_pred"]),
            "metrics": f["metrics"],
            "kpis": f["kpis"],
            "series": f["series"],
        })

    # Total rows and windows
    total_raw_rows = sum(len(f["df_raw"]) for f in file_results)
    total_windows = sum(len(f["df_pred"]) for f in file_results)

    summary = {
        "run_id": run_id,
        "batch_size": len(file_results),
        "window_count": total_windows,
        "total_raw_rows": total_raw_rows,
        "has_ground_truth": has_truth,
        "damage_accuracy": damage_acc,
        "stress_accuracy": stress_acc,
        "macro_f1": macro_f1,
        "mean_confidence": confidence,
    }

    # Save combined predictions if work_dir provided
    if work_dir:
        try:
            combined_dfs = []
            for f in file_results:
                cdf = f["df_pred"].copy()
                cdf.insert(0, "borehole_id", f.get("borehole_id", ""))
                cdf.insert(1, "source_file", f["file_name"])
                combined_dfs.append(cdf)
            if combined_dfs:
                all_preds = pd.concat(combined_dfs, ignore_index=True)
                all_preds.to_csv(work_dir / "predictions.csv", index=False, encoding="utf-8-sig")
        except Exception as e:
            logger.warning(f"Failed to write combined predictions.csv: {e}")

    return {
        "run_id": run_id,
        "sourceRunId": run_id,
        "model": model_info,
        "input": {
            "file_name": active_file["file_name"] if len(file_results) == 1 else f"批次共 {len(file_results)} 个钻孔文件",
            "batch_size": len(file_results),
            "row_count": total_raw_rows,
            "has_labels": has_truth,
        },
        "summary": summary,
        "kpis": active_file["kpis"],
        "series": active_file["series"],
        "spatialRoadway": spatial,
        "files": files_summary,
        "overall_metrics": {
            "damage_accuracy": damage_acc,
            "stress_accuracy": stress_acc,
            "macro_f1": macro_f1,
            "confidence": confidence,
            "has_ground_truth": has_truth,
            "batch_size": len(file_results),
        },
        "artifacts": {
            "predictions_csv": f"/api/runs/{run_id}/artifacts/predictions.csv",
        },
    }


def adapt_to_frontend_payload(
    run_id: str,
    df_raw: pd.DataFrame,
    df_pred: pd.DataFrame,
    metrics: Dict[str, Any],
    file_name: str,
) -> Dict[str, Any]:
    """Single file wrapper for backwards compatibility."""
    file_lower = file_name.lower()
    borehole_map = {
        "s00_1": (10, "BH-11"),
        "s10_1": (9, "BH-10"),
        "s20_1": (8, "BH-09"),
        "s30_1": (7, "BH-08"),
        "s40_1": (6, "BH-07"),
        "s99":   (5, "BH-06"),
        "s40":   (4, "BH-05"),
        "s30":   (3, "BH-04"),
        "s20":   (2, "BH-03"),
        "s10":   (1, "BH-02"),
        "s00":   (0, "BH-01"),
    }
    surface_idx = 2
    borehole_id = "BH-03"
    for k, (idx, bid) in borehole_map.items():
        if k in file_lower:
            surface_idx = idx
            borehole_id = bid
            break

    file_result = {
        "file_name": file_name,
        "order_index": 0,
        "borehole_id": borehole_id,
        "surface_index": surface_idx,
        "df_raw": df_raw,
        "df_pred": df_pred,
        "metrics": metrics,
    }
    return adapt_batch_to_frontend_payload(run_id, [file_result])

