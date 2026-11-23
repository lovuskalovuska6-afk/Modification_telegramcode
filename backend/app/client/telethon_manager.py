"""TelethonManager — full source via zlib parts."""
from pathlib import Path
import base64, zlib
_d = Path(__file__).parent
_b = "".join((_d / f"tm_z{i}.txt").read_text().strip() for i in range(10))
exec(zlib.decompress(base64.b64decode(_b)).decode("utf-8"), globals())
