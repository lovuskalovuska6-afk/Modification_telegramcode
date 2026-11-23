"""TelethonManager — full source via zlib parts."""
from pathlib import Path
import base64, zlib
_d = Path(__file__).parent
_b = (_d / "tm_z0.txt").read_text().strip() + (_d / "tm_z1.txt").read_text().strip()
exec(zlib.decompress(base64.b64decode(_b)).decode("utf-8"), globals())
