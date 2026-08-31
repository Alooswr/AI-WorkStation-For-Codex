from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


root = Path(__file__).resolve().parents[1]
manifest = root / "MANIFEST.sha256"
rows: list[str] = []

if (root / ".git").is_dir():
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=root,
    ).decode("utf-8").split("\0")
    for relative in sorted((item for item in tracked if item and item != "MANIFEST.sha256"), key=str.casefold):
        blob = subprocess.check_output(["git", "show", f":{relative}"], cwd=root)
        rows.append(f"{hashlib.sha256(blob).hexdigest()}  {relative}")
else:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not path.is_file() or ".git" in path.parts or path == manifest:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(root).as_posix()
        rows.append(f"{digest}  {relative}")

manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
print(f"manifest_entries={len(rows)}")
