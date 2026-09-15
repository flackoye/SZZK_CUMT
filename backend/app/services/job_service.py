"""Async job management service for inference tasks."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any
import uuid

import pandas as pd

from app.config import RUNTIME_DIR, DEVICE
from app.core.preprocessing import prepare_sliding_windows, validate_dataframe
from app.core.inference import run_model_inference
from app.core.metrics import compute_summary_metrics
from app.services.model_service import model_service
from app.services.result_adapter import adapt_batch_to_frontend_payload, adapt_to_frontend_payload

logger = logging.getLogger("szic.job_service")
_executor = ThreadPoolExecutor(max_workers=2)

CANONICAL_ORDER_MAP = {
    "vtest_s00.csv":   (0, "BH-01", 0),
    "vtest_s00_1.csv": (1, "BH-11", 10),
    "vtest_s10.csv":   (2, "BH-02", 1),
    "vtest_s10_1.csv": (3, "BH-10", 9),
    "vtest_s20.csv":   (4, "BH-03", 2),
    "vtest_s20_1.csv": (5, "BH-09", 8),
    "vtest_s30.csv":   (6, "BH-04", 3),
    "vtest_s30_1.csv": (7, "BH-08", 7),
    "vtest_s40.csv":   (8, "BH-05", 4),
    "vtest_s40_1.csv": (9, "BH-07", 6),
    "vtest_s99.csv":   (10, "BH-06", 5),
}


def resolve_borehole_meta(file_name: str) -> tuple[int, str, int]:
    base = Path(file_name).name.lower()
    if base in CANONICAL_ORDER_MAP:
        return CANONICAL_ORDER_MAP[base]
    for key, val in CANONICAL_ORDER_MAP.items():
        stem = key.replace(".csv", "")
        if stem in base:
            return val
    return (999, "BH-01", 0)


class JobInfo:
    def __init__(
        self,
        run_id: str,
        file_items: List[Dict[str, Any]],
        work_dir: Path,
        manifest: Optional[Dict[str, Any]] = None,
    ):
        self.run_id = run_id
        self.file_items = file_items
        self.work_dir = work_dir
        self.manifest = manifest
        self.file_names = [item["file_name"] for item in file_items]
        self.file_name = self.file_names[0] if self.file_names else ""
        self.raw_path = file_items[0]["raw_path"] if file_items else None
        self.status = "queued"  # queued | running | succeeded | failed
        self.stage = "uploaded"  # uploaded | validating | preprocessing | inference | aggregating | completed
        self.progress = 0
        self.message = f"批次任务已接收，包含 {len(file_items)} 个钻孔文件，等待执行"
        self.error: Optional[str] = None
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self.result_payload: Optional[Dict[str, Any]] = None

    def to_status_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class JobService:
    _instance: Optional[JobService] = None

    def __init__(self):
        self._jobs: Dict[str, JobInfo] = {}

    @classmethod
    def get_instance(cls) -> JobService:
        if cls._instance is None:
            cls._instance = JobService()
        return cls._instance

    def create_job(
        self,
        file_items_data: List[tuple[str, bytes]],
        manifest: Optional[Dict[str, Any]] = None,
    ) -> JobInfo:
        run_id = uuid.uuid4().hex[:12]
        work_dir = RUNTIME_DIR / run_id
        inputs_dir = work_dir / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)

        # Build manifest map if provided
        manifest_order = {}
        if manifest and "files" in manifest and isinstance(manifest["files"], list):
            for m_item in manifest["files"]:
                if isinstance(m_item, dict) and "file_name" in m_item:
                    manifest_order[m_item["file_name"].lower()] = m_item

        file_items = []
        for file_name, file_bytes in file_items_data:
            dest_path = inputs_dir / file_name
            dest_path.write_bytes(file_bytes)

            canonical_order, default_bh_id, default_surf_idx = resolve_borehole_meta(file_name)
            m_item = manifest_order.get(file_name.lower())
            order_idx = m_item.get("order_index", canonical_order) if m_item else canonical_order
            bh_id = m_item.get("borehole_id", default_bh_id) if m_item else default_bh_id
            surf_idx = m_item.get("surfaceIndex", default_surf_idx) if m_item else default_surf_idx

            file_items.append({
                "file_name": file_name,
                "raw_path": dest_path,
                "order_index": order_idx,
                "borehole_id": bh_id,
                "surface_index": surf_idx,
            })

        # Sort files deterministically according to order_index
        file_items.sort(key=lambda x: x["order_index"])

        # Also write the primary input.csv for backward compatibility
        if file_items:
            (work_dir / "input.csv").write_bytes(file_items[0]["raw_path"].read_bytes())

        job = JobInfo(run_id, file_items, work_dir, manifest)
        self._jobs[run_id] = job

        # Schedule execution in background
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(_executor, self._run_pipeline, job)
        except RuntimeError:
            _executor.submit(self._run_pipeline, job)

        return job

    def get_job(self, run_id: str) -> Optional[JobInfo]:
        if run_id in self._jobs:
            return self._jobs[run_id]

        # Disk recovery fallback
        work_dir = RUNTIME_DIR / run_id
        result_file = work_dir / "result.json"
        if result_file.exists():
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                file_name = data.get("input", {}).get("file_name", "restored.csv")
                dummy_items = [{"file_name": file_name, "raw_path": work_dir / "input.csv", "order_index": 0, "borehole_id": "BH-01", "surface_index": 0}]
                job = JobInfo(run_id, dummy_items, work_dir)
                job.status = "succeeded"
                job.stage = "completed"
                job.progress = 100
                job.message = "模型推理与数据适配全部完成 (从归档恢复)"
                job.result_payload = data
                self._jobs[run_id] = job
                return job
            except Exception as e:
                logger.warning(f"Failed to restore job {run_id} from disk: {e}")
        return None

    def _run_pipeline(self, job: JobInfo) -> None:
        log_file = job.work_dir / "execution.log"
        with open(log_file, "a", encoding="utf-8") as log:
            def log_msg(msg: str):
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                line = f"[{ts}] {msg}"
                log.write(line + "\n")
                log.flush()
                logger.info(f"[{job.run_id}] {msg}")

            try:
                job.status = "running"
                total_files = len(job.file_items)
                log_msg(f"开始执行批次推理任务，共 {total_files} 个文件")

                file_results = []

                for idx, item in enumerate(job.file_items):
                    file_name = item["file_name"]
                    raw_path = item["raw_path"]
                    borehole_id = item["borehole_id"]
                    surface_index = item["surface_index"]
                    order_index = item["order_index"]

                    file_start_pct = int((idx / total_files) * 85)
                    job.stage = f"processing_file_{idx + 1}"
                    job.progress = max(5, file_start_pct)
                    job.message = f"[{idx + 1}/{total_files}] 正在预处理与推理 {file_name} ({borehole_id})..."
                    log_msg(f"[{idx + 1}/{total_files}] 开始处理文件: {file_name} (钻孔: {borehole_id}, 环向: {surface_index})")

                    # 1. Validation
                    df_raw = pd.read_csv(raw_path, encoding="utf-8-sig")
                    validate_dataframe(df_raw)

                    # 2. Preprocessing
                    seq_arr, phys_arr, meta_df = prepare_sliding_windows(df_raw)

                    # 3. Inference
                    infer_pct = int(((idx + 0.6) / total_files) * 85)
                    job.progress = max(job.progress, infer_pct)
                    model, checkpoint = model_service.get_model_and_checkpoint()
                    df_pred = run_model_inference(
                        model=model,
                        checkpoint=checkpoint,
                        seq_arr=seq_arr,
                        phys_arr=phys_arr,
                        meta_df=meta_df,
                        device=DEVICE,
                    )

                    # 4. Metrics
                    metrics = compute_summary_metrics(df_pred)
                    log_msg(f"[{idx + 1}/{total_files}] {file_name} 推理完成: 样本数={len(df_pred)}, 损伤Acc={metrics.get('damage_accuracy')}, 应力Acc={metrics.get('stress_accuracy')}")

                    file_results.append({
                        "file_name": file_name,
                        "raw_path": raw_path,
                        "order_index": order_index,
                        "borehole_id": borehole_id,
                        "surface_index": surface_index,
                        "df_raw": df_raw,
                        "df_pred": df_pred,
                        "metrics": metrics,
                    })

                # Stage: Aggregation
                job.stage = "aggregating"
                job.progress = 92
                job.message = f"正在聚合全部 {total_files} 个钻孔反演数据并构建三维数字孪生场..."
                log_msg(job.message)

                result_payload = adapt_batch_to_frontend_payload(
                    run_id=job.run_id,
                    file_results=file_results,
                    work_dir=job.work_dir,
                )
                job.result_payload = result_payload

                # Save result JSON
                result_json_path = job.work_dir / "result.json"
                result_json_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")

                # Stage: Completed
                job.stage = "completed"
                job.progress = 100
                job.status = "succeeded"
                job.message = f"批次共 {total_files} 个钻孔反演计算与数字孪生重构全部完成"
                job.completed_at = datetime.now().isoformat()
                log_msg(f"任务成功完成: {job.completed_at}")

            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                job.message = f"批次推理执行失败: {e}"
                job.completed_at = datetime.now().isoformat()
                log_msg(f"ERROR: {e}")
                logger.error(f"[{job.run_id}] 批次推理执行失败: {e}", exc_info=True)


job_service = JobService.get_instance()

