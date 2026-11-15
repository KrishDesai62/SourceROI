"""Load editable, file-backed datasets and benchmarks. No paid APIs required."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PROJECT = Path(__file__).resolve().parents[1] / "examples" / "finance"
FACT_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9 /()\-]*):\s*(.+?)\s*$")


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def load_project(root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or DEFAULT_PROJECT).expanduser().resolve()
    config_path = root / "project.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"Missing project.json in {root}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    from .live.config import secure_path
    from .live.ingest import MAX_FILE_BYTES, MAX_FILES
    benchmark_path = secure_path(root, config["benchmark"])
    if benchmark_path.stat().st_size > MAX_FILE_BYTES: raise ValueError("Benchmark too large")
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    if not isinstance(benchmark, list) or not benchmark:
        raise ValueError("benchmark.json must be a nonempty JSON array")
    if len({task['id'] for task in benchmark}) != len(benchmark):
        raise ValueError("Benchmark task IDs must be unique")
    sources = config.get("sources", [])
    if len({s['id'] for s in sources}) != len(sources):
        raise ValueError("Data source IDs must be unique")
    documents = []
    for src in sources:
        if float(src.get("price_per_query_usd", 0)) < 0:
            raise ValueError("Source prices cannot be negative")
        folder = (root / src["path"]).resolve()
        if not folder.is_relative_to(root):
            raise ValueError(f"Source path escapes the project folder: {src['path']}")
        if not folder.is_dir():
            raise FileNotFoundError(f"Source folder not found: {folder}")
        for path in sorted([*folder.rglob("*.md"), *folder.rglob("*.txt")]):
            if not path.resolve().is_relative_to(root): raise ValueError("Document escapes project")
            if path.stat().st_size > MAX_FILE_BYTES or len(documents) >= MAX_FILES: raise ValueError("Document resource limit exceeded")
            body = path.read_text(encoding="utf-8")
            lines = body.splitlines()
            title = next((line.lstrip("# ").strip() for line in lines if line.startswith("# ")), path.stem)
            facts: dict[str, str] = {}
            for line in lines:
                match = FACT_PATTERN.fullmatch(line.strip())
                if match:
                    facts[normalize(match.group(1))] = match.group(2).strip()
            rel = path.relative_to(root).as_posix()
            documents.append({
                "id": f"{src['id']}::{path.relative_to(folder).as_posix()}",
                "source_id": src["id"], "title": title, "content": body,
                "facts": facts, "company": facts.get("company", ""),
                "topic": facts.get("topic", ""), "period": facts.get("period", ""),
                "path": rel, "fingerprint": hashlib.sha256(body.encode()).hexdigest(),
                "word_count": len(body.split()),
            })
    return {"root": str(root), "id": config.get("id", "project"),
            "name": config.get("name", "Untitled project"),
            "description": config.get("description", ""),
            "sources": sources, "documents": documents, "benchmark": benchmark}


def file_manifest(project: dict) -> dict[str, str]:
    return {doc["id"]: doc["fingerprint"] for doc in project["documents"]}
