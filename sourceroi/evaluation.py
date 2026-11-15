"""Paired source/document ablations and source-change regression evaluation."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from itertools import combinations
from typing import Any
from .agents import ABSTAIN, answer
from .corpus import file_manifest


def comparable(text: str) -> str:
    """Conservative normalization for exact-answer scoring; not semantic judging."""
    return re.sub(r"\s+", " ", text.strip().lower().replace(",", ""))


def evaluate(project: dict, *, exclude_sources: set[str] | None = None,
             exclude_documents: set[str] | None = None,
             exclude_facts: dict[str, set[str]] | None = None) -> dict[str, Any]:
    exclude_sources = set(exclude_sources or [])
    exclude_documents = set(exclude_documents or [])
    docs = [d for d in project["documents"]
            if d["source_id"] not in exclude_sources and d["id"] not in exclude_documents]
    if exclude_facts:
        docs = [{**d, "facts": {k: v for k, v in d["facts"].items()
                 if k not in exclude_facts.get(d["id"], set())}} for d in docs]
    source_map = {s["id"]: s for s in project["sources"]}
    tasks = []
    for task in project["benchmark"]:
        response = answer(task["question"], docs)
        correct = comparable(response["answer"]) == comparable(str(task["expected"]))
        queried = response["queried_source_ids"]
        # Source lookup prices are hypothetical/configured estimates, not billed API fees.
        modeled_lookup_cost = sum(float(source_map[s].get("price_per_query_usd", 0)) for s in queried)
        # Parallel retrieval assumption; actual network latency not measured in offline mode.
        modeled_source_latency = max([float(source_map[s].get("modeled_latency_ms", 0)) for s in queried], default=0.0)
        tasks.append({
            "id": task["id"], "category": task.get("category", "General"),
            "question": task["question"], "expected": task["expected"],
            "actual": response["answer"], "correct": correct,
            "grounded": response["answer"] != ABSTAIN and bool(response["citation_doc_ids"]),
            "citation_doc_ids": response["citation_doc_ids"],
            "retrieved_doc_ids": response["retrieved_doc_ids"],
            "queried_source_ids": queried, "requested_metric": response["requested_metric"],
            "source_lookup_cost_usd": round(modeled_lookup_cost, 6),
            "modeled_latency_ms": round(modeled_source_latency, 2),
            "local_compute_ms": round(response["compute_ms"], 4),
            "approx_context_tokens": response["estimate_tokens"],
        })
    n = len(tasks)
    passed = sum(t["correct"] for t in tasks)
    total_cost = sum(t["source_lookup_cost_usd"] for t in tasks)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": project["id"],
        "configuration": {"exclude_sources": sorted(exclude_sources),
                          "exclude_documents": sorted(exclude_documents)},
        "metrics": {
            "task_count": n, "passed": passed, "failed": n - passed,
            "accuracy": round(passed / n, 4) if n else 0.0,
            "grounded_rate": round(sum(t["grounded"] for t in tasks) / n, 4) if n else 0.0,
            "estimated_total_source_cost_usd": round(total_cost, 6),
            "estimated_cost_per_task_usd": round(total_cost / n, 6) if n else 0.0,
            "mean_modeled_source_latency_ms": round(sum(t["modeled_latency_ms"] for t in tasks) / n, 2) if n else 0,
            "mean_measured_local_compute_ms": round(sum(t["local_compute_ms"] for t in tasks) / n, 4) if n else 0,
            "mean_approx_context_tokens": round(sum(t["approx_context_tokens"] for t in tasks) / n) if n else 0,
        },
        "tasks": tasks,
    }


def differences(base: dict, other: dict) -> dict:
    left = {t["id"]: t for t in base["tasks"]}
    right = {t["id"]: t for t in other["tasks"]}
    lost = [id for id, t in left.items() if t["correct"] and id in right and not right[id]["correct"]]
    gained = [id for id, t in left.items() if not t["correct"] and id in right and right[id]["correct"]]
    b, o = base["metrics"], other["metrics"]
    return {
        "lost_task_ids": lost, "gained_task_ids": gained,
        "delta_accuracy_pct_points": round((o["accuracy"] - b["accuracy"]) * 100, 2),
        "delta_cost_usd": round(o["estimated_total_source_cost_usd"] - b["estimated_total_source_cost_usd"], 6),
        "delta_latency_ms": round(o["mean_modeled_source_latency_ms"] - b["mean_modeled_source_latency_ms"], 2),
        "lost_count": len(lost), "gained_count": len(gained),
    }


def ablation_study(project: dict, base: dict | None = None) -> dict:
    base = base or evaluate(project)
    source_rows = []
    for s in project["sources"]:
        result = evaluate(project, exclude_sources={s["id"]})
        delta = differences(base, result)
        source_rows.append({"source_id": s["id"], "source_name": s["name"],
                            "accuracy_without": result["metrics"]["accuracy"],
                            "cost_without": result["metrics"]["estimated_total_source_cost_usd"],
                            "saved_cost_usd": round(-delta["delta_cost_usd"], 6),
                            "lost_tasks": delta["lost_task_ids"], "gained_tasks": delta["gained_task_ids"],
                            "delta_accuracy_pct_points": delta["delta_accuracy_pct_points"]})
    document_rows = []
    for doc in project["documents"]:
        result = evaluate(project, exclude_documents={doc["id"]})
        delta = differences(base, result)
        document_rows.append({"doc_id": doc["id"], "title": doc["title"],
                              "source_id": doc["source_id"], "lost_tasks": delta["lost_task_ids"],
                              "gained_tasks": delta["gained_task_ids"],
                              "delta_accuracy_pct_points": delta["delta_accuracy_pct_points"]})
    document_rows.sort(key=lambda row: (-len(row["lost_tasks"]), row["doc_id"]))
    source_rows.sort(key=lambda row: (-len(row["lost_tasks"]), row["source_id"]))
    fact_rows = []
    for doc in project["documents"]:
        for key, value in doc["facts"].items():
            if key in {"company", "topic", "period", "document type", "source", "published"}:
                continue
            result = evaluate(project, exclude_facts={doc["id"]: {key}})
            delta = differences(base, result)
            fact_rows.append({"doc_id": doc["id"], "title": doc["title"],
                              "source_id": doc["source_id"], "field": key,
                              "value": value, "lost_tasks": delta["lost_task_ids"],
                              "gained_tasks": delta["gained_task_ids"]})
    fact_rows.sort(key=lambda row: (-len(row["lost_tasks"]), row["doc_id"], row["field"]))
    return {"sources": source_rows, "documents": document_rows, "facts": fact_rows,
            "disclaimer": "Single-source/document ablations measure changes on this benchmark only. They do not establish universal causal importance or account for all interactions."}


def change_report(saved: dict, current: dict, project: dict) -> dict:
    before = saved.get("report")
    if not isinstance(before, dict) or before.get("project_id") != project["id"]:
        raise ValueError("Saved baseline belongs to a different project or is invalid")
    old = saved.get("manifest", {})
    now = file_manifest(project)
    changed = sorted(k for k in set(old) & set(now) if old[k] != now[k])
    return {
        "diff": differences(before, current),
        "files_changed": changed, "files_added": sorted(set(now) - set(old)),
        "files_removed": sorted(set(old) - set(now)),
        "baseline_created_at": saved.get("saved_at"),
        "baseline_metrics": before["metrics"],
        "current_metrics": current["metrics"],
    }


def optimize_portfolio(project: dict, quality_floor: float = .85) -> dict:
    """Exhaustive source selection for small demo projects (not a global optimum for >8 sources).

    Find the least expensive *modeled* configuration meeting a benchmark accuracy floor.
    Costs are per-run proxy estimates; fixed subscription costs are not included.
    """
    ids = [s["id"] for s in project["sources"]]
    if len(ids) > 8:
        raise ValueError("Portfolio enumeration is limited to 8 sources in v0")
    rows = []
    for r in range(len(ids) + 1):
        for active in combinations(ids, r):
            active_set = set(active)
            result = evaluate(project, exclude_sources=set(ids) - active_set)
            m = result["metrics"]
            rows.append({"source_ids": list(active), "accuracy": m["accuracy"],
                         "passed": m["passed"], "cost_usd": m["estimated_total_source_cost_usd"],
                         "latency_ms": m["mean_modeled_source_latency_ms"]})
    eligible = [r for r in rows if r["accuracy"] >= quality_floor]
    best = min(eligible, key=lambda r: (r["cost_usd"], -r["accuracy"], r["latency_ms"])) if eligible else None
    frontier = [r for r in rows if not any(
        (x["cost_usd"] <= r["cost_usd"] and x["accuracy"] >= r["accuracy"] and
         (x["cost_usd"] < r["cost_usd"] or x["accuracy"] > r["accuracy"]))
        for x in rows)]
    frontier.sort(key=lambda r: (r["cost_usd"], -r["accuracy"]))
    return {"quality_floor": quality_floor, "best": best, "frontier": frontier,
            "configurations_tested": len(rows),
            "disclaimer": "Synthetic per-query costs and a small, fixed offline benchmark. This does not include subscriptions, data licenses, or generalize beyond benchmark tasks."}
