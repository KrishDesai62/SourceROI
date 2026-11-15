"""Local baseline snapshots, stored only inside the project folder."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from .corpus import file_manifest


def baseline_path(project: dict) -> Path:
    from .live.config import secure_path
    return secure_path(Path(project["root"]), ".sourceroi/baseline.json", must_exist=False)


def read_baseline(project: dict) -> dict | None:
    path = baseline_path(project)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def save_baseline(project: dict, report: dict) -> str:
    path = baseline_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"saved_at": datetime.now(timezone.utc).isoformat(),
            "manifest": file_manifest(project), "report": report}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return str(path)
