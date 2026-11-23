from pathlib import Path
import base64, zlib
_d = Path(__file__).parent
src = b"".join(zlib.decompress(base64.b64decode((_d / f"tm_z{i}.b64").read_text().strip())) for i in (0, 1))
exec(src.decode("utf-8"), globals())
