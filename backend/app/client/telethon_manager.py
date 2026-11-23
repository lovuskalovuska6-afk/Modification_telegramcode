from pathlib import Path
_d = Path(__file__).parent
exec((_d/"tm_p0.py").read_text() + (_d/"tm_p1.py").read_text(), globals())
