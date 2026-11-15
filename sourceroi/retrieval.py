"""Small local lexical retriever. Replaceable with any customer RAG stack."""
from __future__ import annotations

import math
import re
from collections import Counter

STOP = frozenset("the a an to in on of for is what was were does did how much estimate latest which as and with from report that company market's".split())


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def rank_documents(question: str, docs: list[dict], k: int = 5) -> list[dict]:
    """BM25-style ranking plus a modest title/entity boost."""
    if not docs:
        return []
    q = set(tokenize(question))
    doc_tokens = [tokenize(d["title"] + " " + d["content"]) for d in docs]
    dfs = Counter(w for toks in doc_tokens for w in set(toks))
    avg_len = sum(map(len, doc_tokens)) / len(docs) or 1
    scores = []
    for doc, words in zip(docs, doc_tokens):
        counts = Counter(words)
        score = 0.0
        for term in q:
            if term not in counts:
                continue
            idf = math.log(1 + (len(docs) - dfs[term] + .5) / (dfs[term] + .5))
            tf = counts[term]
            score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * len(words) / avg_len))
        entity = (doc.get("company") or doc.get("topic") or "").lower()
        if entity and entity in question.lower():
            score += 7.0
        scores.append((score, doc))
    scores.sort(key=lambda v: (-v[0], v[1]["id"]))
    return [doc for score, doc in scores[:k] if score > 0]
