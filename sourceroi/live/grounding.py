"""Semantic support scoring from explicit human claim adjudications.

Exact quote validation checks review integrity, not semantic entailment. Verdicts
are supplied by reviewers and must never be generated from citation frequency.
"""
from __future__ import annotations
import hashlib
import json


def evidence_key(question, answer, context):
    payload = {'question': question, 'answer': answer,
               'context': [{'id': c['id'], 'text': c['text']} for c in context]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def review_item(question, answer, context):
    return {'key': evidence_key(question, answer, context), 'question': question, 'answer': answer,
            'context': [{'id': c['id'], 'text': c['text']} for c in context],
            'reviewer': None, 'claims': [], 'status': 'pending'}


def score_review(question, answer, context, citations, reviews):
    item = review_item(question, answer, context)
    review = reviews.get(item['key'])
    unavailable = {'groundedness': None, 'unsupported_claims': None,
                   'grounding_method': 'unreviewed', 'grounding_review_key': item['key']}
    if review is None:
        return unavailable
    if review.get('status') != 'complete' or not str(review.get('reviewer') or '').strip():
        raise ValueError('Grounding review must be complete and identify its reviewer')
    claims = review.get('claims')
    if not isinstance(claims, list) or not claims:
        raise ValueError('Grounding review requires claim spans covering the answer')
    covered = set()
    support = 0
    known = {c['id']: c['text'] for c in context}
    for claim in claims:
        start, end = claim.get('start'), claim.get('end')
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(answer):
            raise ValueError('Invalid claim span')
        span = set(range(start, end))
        if covered & span:
            raise ValueError('Claim spans overlap')
        covered |= span
        verdict = claim.get('verdict')
        if verdict not in ('supported', 'unsupported', 'contradicted'):
            raise ValueError('Claim verdict must be supported, unsupported, or contradicted')
        if verdict == 'supported':
            evidence = claim.get('evidence')
            if not isinstance(evidence, list) or not evidence:
                raise ValueError('Supported claims require cited evidence')
            for reference in evidence:
                cid, quote = reference.get('id'), reference.get('quote')
                if cid not in known or cid not in citations or not isinstance(quote, str) or not quote.strip() or quote not in known[cid]:
                    raise ValueError('Reviewed support must quote actually supplied, cited context')
            support += 1
    if any(not ch.isspace() and i not in covered for i, ch in enumerate(answer)):
        raise ValueError('Claim review does not cover the full answer')
    return {'groundedness': support/len(claims), 'unsupported_claims': len(claims)-support,
            'grounding_method': 'human_claim_adjudication', 'grounding_review_key': item['key']}


def load_reviews(path):
    from pathlib import Path
    data = json.loads(Path(path).read_text())
    items = data.get('items')
    if not isinstance(items, list):
        raise ValueError('Review packet must contain an items list')
    completed = [i for i in items if i.get('status') == 'complete']
    keys = [i.get('key') for i in completed]
    if any(not isinstance(k, str) for k in keys) or len(keys) != len(set(keys)):
        raise ValueError('Completed review keys must be unique strings')
    return dict(zip(keys, completed))
