import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_int(name: str, default: int = 0) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Читаем напрямую из os.environ — надёжнее на Render
    API_ID: int = _env_int("API_ID", 0)
    API_HASH: str = _env_str("API_HASH", "")

    MOCK: str = _env_str("MOCK", "")

    HOST: str = _env_str("HOST", "0.0.0.0")
    PORT: int = _env_int("PORT", 8000)

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    SESSIONS_DIR: Path = BASE_DIR / "sessions"

    @property
    def is_mock(self) -> bool:
        val = (self.MOCK or "").strip().lower()
        if val in ("1", "true", "yes", "on"):
            return True
        if val in ("0", "false", "no", "off"):
            return False
        return not self.has_api_keys

    @property
    def has_api_keys(self) -> bool:
        return bool(self.API_ID and self.API_HASH)


settings = Settings()
