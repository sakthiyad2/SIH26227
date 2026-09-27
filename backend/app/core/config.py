import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    offline_mode: bool = os.getenv("OFFLINE_MODE", "true").lower() == "true"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./backend/data/satellite.db")
    model_dir: Path = Path(os.getenv("MODEL_DIR", "./backend/models")).resolve()
    data_dir: Path = Path(os.getenv("DATA_DIR", "./backend/data")).resolve()
    index_dir: Path = Path(os.getenv("INDEX_DIR", "./backend/indexes")).resolve()
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "local_fallback")
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.55"))
    change_threshold: float = float(os.getenv("CHANGE_THRESHOLD", "0.12"))
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")


settings = Settings()
