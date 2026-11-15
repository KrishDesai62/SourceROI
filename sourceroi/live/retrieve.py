"""Simple transparent BM25 lexical RAG baseline; replaceable by a customer's retrieval adapter."""
from __future__ import annotations
import math
import re
from collections import Counter

STOP = {'a','an','and','are','as','at','be','by','for','from','has','how','in','is','it','of','on','or','the','to','was','were','what','which','with','year','please','tell','me'}


def tokens(text: str) -> list[str]:
    return [w for w in re.findall(r'[\w.%-]+', text.lower()) if w not in STOP and len(w) > 1]


def _search_in_process(question: str, chunks: list[dict], k: int = 5) -> list[dict]:
    if not chunks:
        return []
    query = set(tokens(question))
    if not query:
        return []
    bags = [Counter(tokens(chunk['text'] + ' ' + chunk['title'])) for chunk in chunks]
    df = Counter(term for bag in bags for term in bag)
    avg_len = max(1, sum(sum(bag.values()) for bag in bags) / len(bags))
    result = []
    for chunk, bag in zip(chunks, bags):
        score = 0.0
        dl = sum(bag.values())
        for term in query:
            if term not in bag:
                continue
            idf = math.log(1 + (len(chunks)-df[term]+.5)/(df[term]+.5))
            score += idf * (bag[term] * 2.2) / (bag[term] + 1.2 * (.25+.75*dl/avg_len))
        if score > 0:
            result.append((score, chunk))
    result.sort(key=lambda pair: (-pair[0], pair[1]['id']))
    return [{**c, 'score': round(s, 5)} for s, c in result[:k]]


def search(question: str,chunks: list[dict],k: int=5):
    from .analysis_boundary import active,call
    if active():return _search_in_process(question,chunks,k)
    if type(k) is not int or not 0<=k<=50000:raise ValueError('Invalid bounded retrieval count')
    return call('search',question=question,chunks=chunks,k=k)
