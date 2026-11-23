"""Assemble TelethonManager from source chunks."""
from pathlib import Path
_dir = Path(__file__).parent
_code = "".join((_dir / f"mgr_src_{i}.txt").read_text() for i in range(6))
exec(_code, globals())
