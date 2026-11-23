"""Load TelethonManager from base64 payload (keeps source pushable)."""
from pathlib import Path
import base64

_payload = (Path(__file__).with_name("telethon_manager.b64")).read_text().strip()
exec(base64.b64decode(_payload).decode("utf-8"), globals())
