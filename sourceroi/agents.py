"""Deterministic extractive agent for fully offline, honest demo evaluations.

Does NOT use benchmark expected answers; it only sees questions and source files.
This is intentionally NOT a general-purpose LLM. The integration seam is answer().
"""
from __future__ import annotations

import re
from time import perf_counter
from .corpus import normalize
from .retrieval import rank_documents

RESERVED = {"company", "topic", "period", "document type", "source", "published"}
ABSTAIN = "INSUFFICIENT_EVIDENCE"


def metric_for_question(question: str, documents: list[dict]) -> str | None:
    normalized = normalize(question)
    without_year = re.sub(r"\b(?:fy)?20\d{2}\b", " ", normalized)
    without_year = re.sub(r"\s+", " ", without_year).strip()
    keys = {
        key for doc in documents for key in doc["facts"]
        if key not in RESERVED and len(key) >= 3
    }
    # Match longest specific key first, avoiding 'revenue' over 'net revenue retention'.
    matches = [key for key in keys if any(re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", version) for version in (normalized, without_year))]
    if matches:
        return sorted(matches, key=lambda s: (-len(s), s))[0]
    # Some phrases have the key nested inside the question in a different order.
    return None


def answer(question: str, documents: list[dict], max_docs: int = 5) -> dict:
    started = perf_counter()
    ranked = rank_documents(question, documents, k=max_docs)
    metric = metric_for_question(question, documents)
    question_normal = normalize(question)
    candidates = []
    if metric:
        for rank, doc in enumerate(ranked):
            if metric not in doc["facts"]:
                continue
            entity = doc["company"] or doc["topic"]
            # Do not answer one company's question using another company's data.
            if entity and normalize(entity) not in question_normal:
                continue
            label = f"{doc['period']} {metric}"
            requested_years = set(re.findall(r"(?:fy)?20\d{2}", question_normal))
            # Explicit years must match either document period OR the field label.
            if requested_years:
                available_years = set(re.findall(r"(?:fy)?20\d{2}", normalize(label)))
                # Guidance fields may use FY2026 in an FY2025 earnings call.
                if not requested_years.issubset(available_years):
                    continue
            candidates.append((rank, doc, doc["facts"][metric]))
    result = candidates[0] if candidates else None
    selected = [d["id"] for d in ranked]
    # Naive fan-out policy: query every available source with documents on the named entity.
    # This is a deliberately modeled retrieval strategy, NOT measured paid API traffic.
    source_ids = list(dict.fromkeys(
        d["source_id"] for d in documents
        if (d["company"] or d["topic"]) and normalize(d["company"] or d["topic"]) in question_normal
    ))
    # An offline proxy for approximate prompt volume, NOT actual billed tokens.
    estimated_tokens = round(sum(len(d["content"]) for d in ranked) / 4 + len(question) / 4)
    return {
        "answer": result[2] if result else ABSTAIN,
        "citation_doc_ids": [result[1]["id"]] if result else [],
        "retrieved_doc_ids": selected,
        "queried_source_ids": source_ids,
        "requested_metric": metric,
        "estimate_tokens": estimated_tokens,
        "compute_ms": (perf_counter() - started) * 1000,
        "mode": "offline-extractive",
    }
