from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """App settings. Override with env vars prefixed OPTICORE_ (or a backend/.env file)."""

    model_config = SettingsConfigDict(env_prefix="OPTICORE_", env_file=BACKEND_DIR / ".env", extra="ignore")

    # Local dev default matches docker-compose.yml. Not a production credential.
    database_url: str = "postgresql+psycopg://opticore:opticore_dev@localhost:5432/opticore"
    storage_dir: Path = BACKEND_DIR / "storage"
    max_upload_mb: int = 200
    cors_origins: list[str] = ["http://localhost:4200"]
    # External DWG → DXF converter (LibreDWG `dwg2dxf`). Run as a separate program, never bundled
    # (GPL — see docs/adr/0001-dwg-conversion.md). Not set → DWG uploads fail with a clear message.
    dwg2dxf_path: Path | None = None
    dwg_convert_timeout_s: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
