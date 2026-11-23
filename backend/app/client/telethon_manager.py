"""TelethonManager — assembled from part files."""
from pathlib import Path
_dir = Path(__file__).parent
_parts = []
for _i in range(7):
    _parts.append((_dir / f"mgr_part_{_i}.txt").read_text())
exec("".join(_parts), globals())
