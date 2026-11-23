"""Assemble TelethonManager from base64 source chunks."""
from pathlib import Path
import base64

_dir = Path(__file__).parent
_parts = []
for _i in range(6):
    _parts.append(base64.b64decode((_dir / f"mgr_src_{_i}.b64").read_text().strip()).decode("utf-8"))
exec("".join(_parts), globals())
