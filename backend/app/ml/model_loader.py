from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass
class ModelInfo:
    name: str
    version: str
    source: str
    license: str
    local_path: str


class ModelLoader:
    def __init__(self) -> None:
        self.model_dir = settings.model_dir
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            name="LocalHistogramBaseline",
            version="0.1.0",
            source="experimental color-histogram fallback; not a multimodal model",
            license="Project license not specified",
            local_path=str(self.model_dir),
        )

    def ensure_model_present(self) -> bool:
        return self.model_dir.exists()
