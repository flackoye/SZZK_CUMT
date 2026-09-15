"""Inference task execution and result query endpoints."""
import json
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse

from app.config import MAX_UPLOAD_SIZE_BYTES, ALLOWED_EXTENSIONS
from app.schemas import CreateRunResponse, RunStatusResponse, RunResultResponse
from app.services.job_service import job_service

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=CreateRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    manifest: Optional[str] = Form(None),
):
    """Upload batch of CSV files (or single file) and create an asynchronous inference task."""
    upload_list: List[UploadFile] = []
    if files is not None and len(files) > 0:
        upload_list = files
    elif file is not None:
        upload_list = [file]

    if not upload_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择至少一个 CSV 随钻数据文件进行上传",
        )

    # Filter and validate files
    parsed_manifest = None
    if manifest:
        try:
            parsed_manifest = json.loads(manifest)
        except Exception:
            pass

    file_items_data: List[tuple[str, bytes]] = []
    for f in upload_list:
        ext = Path(f.filename).suffix.lower()
        if ext == ".xlsx":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"检测到文件 '{f.filename}' 为 Excel 格式。请勿上传 .xlsx 文件，请仅上传 11 个标准随钻 .csv 文件",
            )
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式 '{ext}' (来自 '{f.filename}')。仅支持 {list(ALLOWED_EXTENSIONS)}",
            )

        f_bytes = await f.read()
        if len(f_bytes) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件 '{f.filename}' 大小 ({len(f_bytes) / 1024 / 1024:.1f} MB) 超过限制 (50 MB)",
            )
        if len(f_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"上传的文件 '{f.filename}' 为空",
            )
        file_items_data.append((f.filename, f_bytes))

    job = job_service.create_job(file_items_data, manifest=parsed_manifest)

    return CreateRunResponse(
        run_id=job.run_id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        batch_size=len(job.file_items),
        files=job.file_names,
        created_at=job.created_at,
    )


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str):
    """Query task progress and status."""
    job = job_service.get_job(run_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 '{run_id}' 不存在",
        )
    return RunStatusResponse(**job.to_status_dict())


@router.get("/{run_id}/result", response_model=RunResultResponse)
async def get_run_result(run_id: str):
    """Retrieve full inference result and adapted payload for frontend."""
    job = job_service.get_job(run_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 '{run_id}' 不存在",
        )

    if job.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"任务执行失败: {job.error}",
        )

    if job.status != "succeeded" or not job.result_payload:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"任务尚未完成，当前状态: {job.status} (阶段: {job.stage}, 进度: {job.progress}%)",
        )

    return RunResultResponse(**job.result_payload)


@router.get("/{run_id}/artifacts/{file_name}")
async def get_run_artifact(run_id: str, file_name: str):
    """Download task artifact file (e.g. predictions.csv)."""
    job = job_service.get_job(run_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 '{run_id}' 不存在",
        )

    target_path = (job.work_dir / file_name).resolve()
    # Path traversal protection
    if not str(target_path).startswith(str(job.work_dir.resolve())):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="非法路径访问")

    if not target_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"文件 '{file_name}' 不存在")

    return FileResponse(target_path, filename=file_name)

