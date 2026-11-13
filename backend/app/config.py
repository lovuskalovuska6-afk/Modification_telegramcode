from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    API_ID: int = 0
    API_HASH: str = ""
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    SESSIONS_DIR: Path = BASE_DIR / "sessions"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
