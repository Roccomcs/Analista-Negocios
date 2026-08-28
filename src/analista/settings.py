from pathlib import Path
import json
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    database: str = "data/negocios.sqlite3"
    output: str = "outputs/cadmo/seguimiento.xlsx"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    overpass_cache_hours: int = Field(24, ge=1)
    max_candidates: int = Field(2000, ge=1, le=2000)
    max_pages: int = Field(2, ge=1, le=10)
    request_timeout: int = Field(20, ge=5, le=120)
    domain_delay: float = Field(2.0, ge=1)
    user_agent: str = "CadmoAnalista/0.1 (+https://www.cadmo.com.ar)"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout: int = Field(180, ge=10, le=600)
    search_enabled: bool = False
    search_storage_rights_confirmed: bool = False
    excel_runtime: str = ".runtime/excel.json"

    def path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else ROOT / path


def load_settings(path: str | None = None) -> Settings:
    target = Path(path) if path else ROOT / "config.local.json"
    return Settings.model_validate(json.loads(target.read_text("utf-8-sig"))) if target.exists() else Settings()
