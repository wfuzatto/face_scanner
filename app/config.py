from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8091
    api_key: str = ""
    dashboard_unauthenticated: bool = False
    allowed_origins: str = "http://127.0.0.1:3080,http://localhost:3080,http://127.0.0.1:8091,http://localhost:8091"
    max_upload_mb: int = 10
    session_ttl_seconds: int = 600
    session_db_path: Path = Path("data/face_scanner.sqlite3")
    ocr_lang: str = "por+eng"
    tesseract_cmd: str = ""
    face_detector_model: Path = Path("models/face_detection_yunet_2023mar.onnx")
    face_detection_threshold: float = 0.85
    name_match_threshold: float = 88.0
    name_review_threshold: float = 72.0
    min_face_ratio: float = 0.12
    min_blur_score: float = 45.0
    debug_store_images: bool = False
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
