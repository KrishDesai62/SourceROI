"""Question-only retrieval policies. No answer keys, task labels, or scores enter selection."""
from __future__ import annotations

import math
import re
from .retrieve import search, tokens


def task_kind(question: str) -> str:
    q = question.lower()
    if re.search(r'\b(compare|versus|vs|change|changed|trend|difference|across|both|minus|subtract)\b', q):
        return 'comparison'
    if re.search(r'\b(and|together|combine|combined)\b', q):
        return 'multi_evidence'
    return 'lookup'


def validate_policy(policy):
    if not isinstance(policy, dict):
        raise ValueError('Retrieval policy must be an object')
    name = policy.get('name', 'original')
    if name not in ('original', 'top_k', 'context_budget', 'threshold', 'cheapest', 'task_aware', 'coverage', 'learned', 'evidence_aware', 'simple_strong', 'passage_coverage', 'predicate'):
        raise ValueError('Unknown retrieval policy')
    for key in ('k', 'chars', 'max_context_tokens'):
        if key in policy and (type(policy[key]) is not int or policy[key] < 1):
            raise ValueError(f'Policy {key} must be a positive integer')
    for key in ('ratio', 'cost_weight', 'coverage_floor'):
        if key in policy and (type(policy[key]) not in (int, float) or not math.isfinite(policy[key]) or not 0 <= policy[key] <= 1):
            raise ValueError(f'Policy {key} must be finite in [0,1]')
    if 'excluded_sources' in policy and (not isinstance(policy['excluded_sources'], list) or not all(isinstance(s, str) for s in policy['excluded_sources'])):
        raise ValueError('Policy excluded_sources must be a list of source IDs')
    if 'fallback' in policy and type(policy['fallback']) is not bool:
        raise ValueError('fallback must be boolean')
    if name == 'learned':
        if not isinstance(policy.get('by_kind', {}), dict):
            raise ValueError('Learned policy requires a mapping')
        for child in policy.get('by_kind', {}).values():
            if not isinstance(child, dict):
                raise ValueError('Learned child policy must be an object')
            if child.get('name') == 'learned':
                raise ValueError('Nested learned policies are not supported')
            validate_policy(child)


def _select_context_in_process(question: str, chunks: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    settings = cfg.get('settings', {})
    policy = settings.get('retrieval_policy', {'name': 'original'})
    validate_policy(policy)
    kind = task_kind(question)
    if policy.get('name') == 'learned':
        policy = policy.get('by_kind', {}).get(kind, {'name': 'original'})
    excluded = set(policy.get('excluded_sources', []))
    if not excluded <= {s['id'] for s in cfg['sources']}:
        raise ValueError('Policy excludes an unknown source')
    oversized=[c['id'] for c in chunks if c.get('chunk_strategy')=='table' and c.get('fragmented')]
    pool = [c for c in chunks if c['source_id'] not in excluded and c['id'] not in oversized]
    limit = int(settings.get('max_chunks', 6))
    name = policy.get('name', 'original')
    # Give every policy the same ranked candidate pool; original preserves its usual top-k.
    ranked = search(question, pool, k=max(limit, min(100, len(pool))))
    k = policy.get('k', limit)
    char_budget = policy.get('chars', settings.get('max_context_chars'))
    evidence_trace = {}
    if name == 'predicate':
        from .facts import select
        selected, evidence_trace = select(pool,cfg.get('_calculation_contract'),cfg,cfg.get('_task_scope'))
        evidence_trace['target_k_exceeded_for_required_facts']=len(selected)>k
    elif name == 'passage_coverage':
        from .evidence import select_passages
        selected, evidence_trace = select_passages(question, ranked, k)
    elif name == 'evidence_aware':
        from .evidence import select_evidence
        selected, evidence_trace = select_evidence(question, ranked, cfg, policy, cfg.get('_context_token_counter'))
    elif name == 'simple_strong':
        selected = ranked[:policy.get('lookup_k', 2)] if kind == 'lookup' else ranked[:k]
    elif name == 'top_k':
        selected = ranked[:k]
    elif name == 'threshold':
        selected = [c for c in ranked if c['score'] >= ranked[0]['score']*policy.get('ratio', .5)][:k] if ranked else []
    elif name == 'cheapest':
        fees = {s['id']: s.get('per_call_price_usd') for s in cfg['sources']}
        # Unknown prices remain unknown: use a documented fixed ID heuristic instead.
        if any(fees.get(c['source_id']) is None for c in ranked):
            raise ValueError('Cheapest-source baseline requires explicit source prices, including zero')
        selected = sorted(ranked, key=lambda c: (fees[c['source_id']], -c['score'], c['id']))[:k]
    elif name == 'task_aware':
        selected = ranked[:(k if kind != 'lookup' else 1)]
    elif name == 'coverage':
        # Greedy query-term coverage with redundancy penalty and configured source fees.
        query = set(tokens(question))
        remaining, selected, covered = ranked[:], [], set()
        fees = {s['id']: s.get('per_call_price_usd') for s in cfg['sources']}
        weight = policy.get('cost_weight', .5)
        if weight and any(fees.get(c['source_id']) is None for c in ranked):
            raise ValueError('Cost-aware coverage requires explicit source prices')
        max_score = ranked[0]['score'] if ranked else 1
        seen_text = set()
        while remaining and len(selected) < k:
            def utility(c):
                text = ' '.join(c['text'].lower().split())
                if text in seen_text:
                    return -1
                terms = set(tokens(c['text'])) & query
                gain = len(terms-covered)/max(1, len(query))
                # A retrieval estimate, never reported as actual token/cost savings.
                redundancy = len(terms & covered)/max(1, len(terms))
                return gain + c['score']/max_score - .5*redundancy - (weight*fees[c['source_id']] if weight else 0)
            best = max(remaining, key=lambda c: (utility(c), c['id']))
            if utility(best) < 0:
                break
            selected.append(best)
            seen_text.add(' '.join(best['text'].lower().split()))
            covered.update(set(tokens(best['text'])) & query)
            remaining.remove(best)
    else:
        selected = ranked[:k]
    if settings.get('deduplicate_passages') or name == 'coverage':
        unique = {}
        for c in selected:
            unique.setdefault(' '.join(c['text'].lower().split()), c)
        selected = list(unique.values())
    if char_budget is not None:
        required_ids = {c['id'] for c in selected}
        kept = []
        for c in selected:
            if len(c['text']) <= char_budget:
                kept.append(c)
                char_budget -= len(c['text'])
        selected = kept
        if name=='predicate' and {c['id'] for c in kept}!=required_ids:
            selected=[]
            evidence_trace['budget_fact_abstention']=True
        # A tight context budget must not hide a retained numerical disagreement.
        kept_ids = {c['id'] for c in selected}
        if any(not set(pair) <= kept_ids for pair in evidence_trace.get('potential_conflicts_preserved', [])):
            selected = []
            evidence_trace['budget_conflict_abstention'] = True
    return selected, {**evidence_trace, 'excluded_oversized_table_ids':oversized,'ranked_ids': [c['id'] for c in ranked], 'task_kind': kind, 'policy': policy, 'candidate_count': len(ranked),
                      'selected_ids': [c['id'] for c in selected],
                      'estimate_note': 'Selection uses retrieval features; savings require returned model usage.'}


def select_context(question,chunks,cfg):
    from .analysis_boundary import active,call
    if active():return _select_context_in_process(question,chunks,cfg)
    if cfg.get('_context_token_counter') is not None:
        if cfg.get('_strict_analysis_isolation'):raise ValueError('Production analytical isolation cannot run an arbitrary tokenizer callback; use a verified bounded transport')
        # Explicit trusted-local callback compatibility, not a production sandbox.
        return _select_context_in_process(question,chunks,cfg)
    public={'sources':cfg['sources'],'settings':cfg.get('settings',{}),'_calculation_contract':cfg.get('_calculation_contract'),'_task_scope':cfg.get('_task_scope')}
    result=call('policy',question=question,chunks=chunks,cfg=public)
    return result[0],result[1]
