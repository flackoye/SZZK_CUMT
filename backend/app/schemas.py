"""Pydantic schemas for API requests and responses."""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    model_ready: bool = False
    model_id: str = "v3-full"
    device: str = "cpu"
    message: Optional[str] = None


class CreateRunResponse(BaseModel):
    run_id: str
    status: str = "queued"
    stage: str = "uploaded"
    progress: int = 0
    batch_size: int = 1
    files: List[str] = []
    created_at: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: str
    stage: str
    progress: int
    message: str
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class DrillingSamplePoint(BaseModel):
    sample_index: int
    depth_cm: float
    torque_nm: float
    thrust_kn: float
    pred_damage_level: int
    pred_stress_mpa: int
    pred_state_label: str
    confidence: float
    true_damage_level: Optional[int] = None
    true_stress_mpa: Optional[int] = None


class RunResultResponse(BaseModel):
    run_id: str
    model: Dict[str, Any]
    input: Dict[str, Any]
    summary: Dict[str, Any]
    kpis: Dict[str, Any]
    series: List[Dict[str, Any]]
    spatialRoadway: Optional[Dict[str, Any]] = None
    ringCloud: Optional[Dict[str, Any]] = None
    dashboardSummary: Optional[Dict[str, Any]] = None
    referencePreview: bool = False
    previewProfile: Optional[str] = None
    files: Optional[List[Dict[str, Any]]] = None
    overall_metrics: Optional[Dict[str, Any]] = None
    artifacts: Dict[str, str]

