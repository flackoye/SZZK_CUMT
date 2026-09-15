"""FastAPI Application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, runs
from app.services.model_service import model_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("szic.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: preload model weights
    logger.info("正在启动 SZIC 随钻模型推理服务...")
    model_service.initialize()
    yield
    # Shutdown
    logger.info("正在停止 SZIC 服务...")


app = FastAPI(
    title="SZIC 随钻智控模型推理平台 API",
    description="提供随钻时序数据多尺度特征提取与 V3-Full (PF-CL-MTIM) 围岩状态物理融合推理服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router)
app.include_router(runs.router)


@app.get("/")
async def root():
    return {
        "service": "SZIC While-Drilling Intelligence Inference API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }

