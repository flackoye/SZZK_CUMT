"""Model singleton management service."""
from __future__ import annotations

import logging
from typing import Optional, Tuple
import torch

from app.config import DEFAULT_MODEL_PATH, DEVICE, DEFAULT_MODEL_ID
from app.core.model import FullModelStandard
from app.core.inference import load_model

logger = logging.getLogger("szic.model_service")


class ModelService:
    _instance: Optional[ModelService] = None
    _model: Optional[FullModelStandard] = None
    _checkpoint: Optional[dict] = None
    _error: Optional[str] = None
    _is_ready: bool = False

    @classmethod
    def get_instance(cls) -> ModelService:
        if cls._instance is None:
            cls._instance = ModelService()
        return cls._instance

    def initialize(self) -> bool:
        """Load model weights and scalers into memory."""
        try:
            logger.info(f"正在加载模型 {DEFAULT_MODEL_ID} 从 {DEFAULT_MODEL_PATH} 到 {DEVICE}...")
            self._model, self._checkpoint = load_model(DEFAULT_MODEL_PATH, DEVICE)
            self._is_ready = True
            self._error = None
            logger.info("模型加载完成并就绪。")
            return True
        except Exception as e:
            self._is_ready = False
            self._error = str(e)
            logger.error(f"模型加载失败: {e}", exc_info=True)
            return False

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def error_message(self) -> Optional[str]:
        return self._error

    def get_model_and_checkpoint(self) -> Tuple[FullModelStandard, dict]:
        if not self._is_ready or self._model is None or self._checkpoint is None:
            raise RuntimeError(f"模型未就绪: {self._error or '未初始化'}")
        return self._model, self._checkpoint


model_service = ModelService.get_instance()

