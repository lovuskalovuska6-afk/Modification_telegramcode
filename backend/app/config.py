from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ключи приложения Telegram: https://my.telegram.org/apps
    API_ID: int = 0
    API_HASH: str = ""

    # true = заглушка, false = реальный Telegram
    # Если не задано: real, когда есть API_ID и API_HASH
    MOCK: str = ""

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    SESSIONS_DIR: Path = BASE_DIR / "sessions"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def is_mock(self) -> bool:
        val = (self.MOCK or "").strip().lower()
        if val in ("1", "true", "yes", "on"):
            return True
        if val in ("0", "false", "no", "off"):
            return False
        # авто: mock если нет ключей
        return not (self.API_ID and self.API_HASH)


settings = Settings()
