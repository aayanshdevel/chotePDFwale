import os
import tempfile
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "OptiPDF Studio — Precision PDF Size Reducer"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"
    API_V1_PREFIX: str = "/api/v1"

    # Upload & Document Safety Limits
    MAX_UPLOAD_SIZE_MB: int = 100
    MAX_PAGE_COUNT: int = 1000
    MAX_BATCH_FILES: int = 20
    UPLOAD_CHUNK_SIZE_BYTES: int = 1024 * 256  # 256 KB streaming chunks

    # Processing & Resource Limits
    MAX_CONCURRENT_JOBS: int = 4
    COMPRESSION_TIMEOUT_SECONDS: int = 120
    GS_TIMEOUT_SECONDS: int = 45
    MAX_TARGET_ITERATIONS: int = 6

    # Temporary Isolated Ephemeral Storage
    STORAGE_DIR: str = os.path.join(tempfile.gettempdir(), "optipdf_ephemeral_store")
    FILE_RETENTION_MINUTES: int = 30
    CLEANUP_INTERVAL_SECONDS: int = 120

    # Security & Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 120
    CORS_ORIGINS: str = "*"

    # Optional static frontend bundle path for single-container / preview serving
    STATIC_FRONTEND_DIR: str = str(
        Path(__file__).resolve().parents[3] / "frontend" / "static_bundle"
    )
    SAMPLE_PDF_DIR: str = str(
        Path(__file__).resolve().parents[3] / "sample_pdfs"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def cors_origin_list(self) -> List[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
