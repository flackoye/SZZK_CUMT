"""Original Mine preview data exposed through the backend API."""
from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/preview", tags=["preview"])

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = _PROJECT_ROOT / "qianduan" / "public" / "data"
_PREVIEW_FILES = {
    "summary": "dashboard_summary.json",
    "ringCloud": "ring_cloud_v4.json",
    "spatialRoadway": "roadway_spatial_v4.json",
}


@lru_cache(maxsize=1)
def _cached_preview_bundle() -> Dict[str, Any]:
    bundle: Dict[str, Any] = {
        "profile": "original-mine-v4",
        "source": "backend",
    }
    for key, file_name in _PREVIEW_FILES.items():
        path = _DATA_DIR / file_name
        if not path.is_file():
            raise FileNotFoundError(f"Missing preview data file: {path}")
        bundle[key] = json.loads(path.read_text(encoding="utf-8"))
    return bundle


def load_preview_bundle() -> Dict[str, Any]:
    """Return an isolated copy so callers cannot mutate the cached baseline."""
    return copy.deepcopy(_cached_preview_bundle())


@router.get("/bootstrap")
async def get_preview_bootstrap() -> Dict[str, Any]:
    """Return the exact data bundle used by the original frontend-only preview."""
    try:
        return load_preview_bundle()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"预览基准数据加载失败: {exc}") from exc
