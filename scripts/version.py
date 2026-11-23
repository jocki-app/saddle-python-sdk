import re,sys
from pathlib import Path
value=sys.argv[1]
if not re.fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?",value):raise SystemExit("Use a Python package version such as 0.2.0 or 0.2.0rc1")
p=Path("pyproject.toml");p.write_text(re.sub(r'^version = "[^"]+"',f'version = "{value}"',p.read_text(),count=1,flags=re.M))
