import json
import sys
from pathlib import Path

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.api.preview import load_preview_bundle
from app.services.result_adapter import adapt_batch_to_frontend_payload, _is_reference_preview_batch


def test_preview_bundle_matches_original_static_contract():
    data_dir = PROJECT_ROOT / "qianduan" / "public" / "data"
    bundle = load_preview_bundle()

    assert bundle["profile"] == "original-mine-v4"
    assert bundle["source"] == "backend"
    assert bundle["summary"] == json.loads(
        (data_dir / "dashboard_summary.json").read_text(encoding="utf-8")
    )
    assert bundle["ringCloud"] == json.loads(
        (data_dir / "ring_cloud_v4.json").read_text(encoding="utf-8")
    )
    assert bundle["spatialRoadway"] == json.loads(
        (data_dir / "roadway_spatial_v4.json").read_text(encoding="utf-8")
    )

    assert len(bundle["ringCloud"]["boreholes"]) == 11
    assert [group["id"] for group in bundle["spatialRoadway"]["groups"]] == ["A", "B", "C"]
    assert all(len(group["boreholes"]) == 11 for group in bundle["spatialRoadway"]["groups"])


def test_preview_bundle_is_returned_as_an_isolated_copy():
    first = load_preview_bundle()
    first["ringCloud"]["meta"]["title"] = "mutated"
    second = load_preview_bundle()
    assert second["ringCloud"]["meta"]["title"] != "mutated"


def test_reference_batch_requires_all_exact_bundled_files():
    golden_dir = PROJECT_ROOT / "qianduan" / "public" / "data" / "golden_batch"
    paths = sorted(golden_dir.glob("*.csv"))
    assert len(paths) == 11

    file_results = [
        {"file_name": path.name, "raw_path": path}
        for path in paths
    ]
    assert _is_reference_preview_batch(file_results)
    assert not _is_reference_preview_batch(file_results[:-1])


def test_reference_batch_adapter_restores_exact_preview_payload():
    golden_dir = PROJECT_ROOT / "qianduan" / "public" / "data" / "golden_batch"
    paths = sorted(golden_dir.glob("*.csv"))
    raw = pd.DataFrame({
        "depth_cm": [0.0, 2.5, 125.0],
        "torque_nm": [10.0, 11.0, 12.0],
        "thrust_kn": [1.0, 1.1, 1.2],
    })
    pred = pd.DataFrame({
        "sample_index": [0, 1, 2],
        "depth_cm": [0.0, 2.5, 125.0],
        "torque_nm": [10.0, 11.0, 12.0],
        "thrust_kn": [1.0, 1.1, 1.2],
        "pred_damage_level": [20, 20, 40],
        "pred_stress_mpa": [10, 20, 30],
        "pred_state_label": ["D20_S10", "D20_S20", "D40_S30"],
        "state_confidence": [0.8, 0.9, 0.85],
        "true_damage_level": [20, 20, 40],
        "true_stress_mpa": [10, 20, 30],
    })
    metrics = {
        "has_ground_truth": True,
        "damage_accuracy": 1.0,
        "stress_accuracy": 1.0,
        "macro_f1": 1.0,
        "mean_confidence": 0.85,
    }
    file_results = [
        {
            "file_name": path.name,
            "raw_path": path,
            "order_index": index,
            "borehole_id": f"BH-{index + 1:02d}",
            "surface_index": index,
            "df_raw": raw,
            "df_pred": pred,
            "metrics": metrics,
        }
        for index, path in enumerate(paths)
    ]

    payload = adapt_batch_to_frontend_payload("contract-test", file_results)
    preview = load_preview_bundle()
    assert payload["referencePreview"] is True
    assert payload["previewProfile"] == "original-mine-v4"
    assert payload["dashboardSummary"] == preview["summary"]
    assert payload["ringCloud"] == preview["ringCloud"]
    assert payload["spatialRoadway"] == preview["spatialRoadway"]
