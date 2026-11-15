"""Conservative, pre-answer evidence selection. Scores are heuristics, not entailment."""
from __future__ import annotations
import re
import time
from .retrieve import tokens


def requirements(question):
    query = set(tokens(question))
    entities = [p.strip() for p in re.findall(r'\b[A-Z][\w-]*(?:\s+(?:[A-Z][\w-]*|[a-z])){0,4}', question)]
    entities = [e for e in entities if e.lower() not in {'what','which','who','where','when','how','are','is','the','in'}]
    parts = [set(tokens(p)) for p in re.split(r'\b(?:and|versus|vs|both)\b', question, flags=re.I) if len(tokens(p)) > 1]
    multi = bool(re.search(r'\b(both|compare|versus|earlier|later|older|younger|difference|between|and)\b', question, re.I))
    return {'terms': query, 'entities': entities, 'parts': parts, 'multiple_documents': multi,
            'years': re.findall(r'\b(?:19|20)\d{2}\b', question)}


def signatures(chunk):
    words = set(tokens(chunk['text']))
    return words, set(re.findall(r'\b\d+(?:[.,]\d+)*\b', chunk['text'])), bool(re.search(r'\b(not|never|no)\b', chunk['text'], re.I))


def near_duplicate(a, b):
    wa, na, neg_a = signatures(a); wb, nb, neg_b = signatures(b)
    # Different quantities or negation may be important contradictions; preserve them.
    return na == nb and neg_a == neg_b and len(wa & wb)/max(1, len(wa | wb)) >= .9


def select_evidence(question, ranked, cfg, policy, token_counter=None):
    started = time.perf_counter()
    original = ranked[:int(cfg.get('settings', {}).get('max_chunks', 5))]
    needs = requirements(question)
    source_meta = {s['id']: s for s in cfg['sources']}
    unique, duplicates = [], []
    for chunk in ranked[:30]:
        if any(near_duplicate(chunk, kept) for kept in unique):
            duplicates.append(chunk['id'])
        else:
            unique.append(chunk)
    selected, covered = [], set()
    conflicts = []
    # Potential disagreement: shared query terms plus differing quantities/negation.
    # This is deliberately labeled a signal, not a verified factual contradiction.
    for i, left in enumerate(original):
        for right in original[i+1:]:
            a, na, neg_a = signatures(left); b, nb, neg_b = signatures(right)
            if len(a & b & needs['terms']) >= 2 and ((na and nb and na != nb) or neg_a != neg_b):
                conflicts.append([left['id'], right['id']])
    k = policy.get('k', len(original))
    available = unique[:]
    while available and len(selected) < k:
        def utility(chunk):
            words = set(tokens(chunk['text']+' '+chunk['title']))
            gain = len((words & needs['terms'])-covered)/max(1, len(needs['terms']))
            reliability = source_meta[chunk['source_id']].get('reliability', .5)
            relevance = chunk['score']/max(ranked[0]['score'] if ranked else 1, 1e-9)
            novelty = 1-max((len(words & set(tokens(c['text'])))/max(1,len(words)) for c in selected),default=0)
            return (gain + .4*relevance + .1*reliability + .2*novelty)/max(1,len(chunk['text'])/600)
        best = max(available, key=lambda c:(utility(c), c['id']))
        words = set(tokens(best['text']+' '+best['title']))
        if selected and not (words & needs['terms'])-covered and (not needs['multiple_documents'] or len({c['document_id'] for c in selected}) >= 2):
            break
        selected.append(best); available.remove(best); covered |= words & needs['terms']
    # Maintain both sides of potential conflicts; do not drop inconvenient evidence.
    protected = {cid for pair in conflicts for cid in pair}
    for chunk in original:
        if chunk['id'] in protected and chunk['id'] not in {c['id'] for c in selected}:
            selected.append(chunk)
    risk = []
    if original and not selected:
        risk.append('selection_empty')
    if needs['terms'] and len(covered)/len(needs['terms']) < policy.get('coverage_floor', .7):
        risk.append('weak_query_coverage')
    if needs['multiple_documents'] and len({c['document_id'] for c in selected}) < 2:
        risk.append('unverified_complementary_document_coverage')
    # Entity anchors are only a conservative warning: unseen entity aliases need fallback.
    available_text = ' '.join(c['title']+' '+c['text'] for c in selected).lower()
    if any(e.lower() not in available_text for e in needs['entities']):
        risk.append('missing_entity_anchor')
    if needs['years']:
        risk.append('temporal_scope_requires_review')
    if conflicts:
        risk.append('potential_conflict_preserved')
    fallback = bool(policy.get('fallback', False) and risk)
    if fallback:
        selected = original
    measured_tokens = None
    if policy.get('max_context_tokens') is not None:
        if token_counter is None:
            raise ValueError('Evidence token budget requires an actual tokenizer capability')
        measured_tokens = token_counter(selected)
        if measured_tokens > policy['max_context_tokens']:
            risk.append('token_budget_infeasible_for_selected_evidence')
            # Never silently exceed the budget, including on the fallback path.
            while selected and measured_tokens > policy['max_context_tokens']:
                selected = selected[:-1]
                measured_tokens = token_counter(selected)
    return selected, {'requirements': {'entities': needs['entities'], 'query_terms': sorted(needs['terms']),
                                       'multiple_documents': needs['multiple_documents'], 'years': needs['years']},
        'coverage_estimate': len(covered)/max(1,len(needs['terms'])), 'uncertainty_signals': risk,
        'fallback_used': fallback, 'fallback_reason': risk if fallback else [],
        'fallback_extra_generation_calls': 0, 'removed_near_duplicates': duplicates,
        'potential_conflicts': conflicts, 'measured_selection_context_tokens': measured_tokens,
        'selection_check_ms': round((time.perf_counter()-started)*1000,3),
        'abstain_without_context': True,
        'limitation': 'Heuristic evidence requirements and potential conflicts do not establish sufficiency, authority, currentness, or factual correctness.'}


def select_passages(question, ranked, k):
    """Greedy query-only passage coverage; no answer/evidence annotations enter.

    Separate comparison operands get a selection opportunity before global fill.
    Scores are lexical heuristics, never semantic approval. Repeated source text
    is removed only within the same source, retaining competing authorities.
    """
    scaffold = {'according', 'document', 'documents', 'notice', 'current', 'using', 'use',
                'does', 'per', 'under', 'many', 'much', 'difference', 'between', 'minus',
                'subtract', 'compare', 'versus', 'both', 'rate', 'value'}
    query = set(tokens(question))-scaffold
    parts = [set(tokens(p))-scaffold for p in re.split(r'\b(?:minus|versus|vs|and)\b', question, flags=re.I)]
    parts = [p for p in parts if p] if re.search(r'\b(?:minus|difference|compare|versus|subtract|both)\b', question, re.I) else []
    unique, removed = [], []
    seen = set()
    for c in ranked:
        key = (c['source_id'], ' '.join(c['text'].lower().split()))
        if key in seen: removed.append(c['id'])
        else: seen.add(key); unique.append(c)
    selected, covered = [], set()
    def utility(c, need):
        words = set(tokens(c['text']))
        # Rare query terms distinguish predicates; title repetition is excluded.
        weights = {w:1+sum(w not in set(tokens(x['text'])) for x in unique)/max(1,len(unique)) for w in need}
        gain = sum(weights[w] for w in words & need)
        return gain/max(1,len(tokens(c['text'])))**.35
    for need in parts:
        pool = [c for c in unique if c not in selected and set(tokens(c['text'])) & need]
        if pool and len(selected) < k:
            best = max(pool, key=lambda c:(utility(c,need), c.get('score',0), c['id']))
            selected.append(best); covered |= set(tokens(best['text'])) & query
    while len(selected) < k:
        need = query-covered if selected else query
        pool = [c for c in unique if c not in selected and set(tokens(c['text'])) & need]
        if not pool: break
        best = max(pool, key=lambda c:(utility(c,need), c.get('score',0), c['id']))
        selected.append(best); covered |= set(tokens(best['text'])) & query
    # Do not gain apparent efficiency by discarding another value of a selected
    # predicate. This narrow signal preserves evidence; it does not resolve it.
    shape = lambda c: re.sub(r'\d+(?:[.,]\d+)*', '<value>', ' '.join(c['text'].lower().split()))
    conflicts = []
    for chosen in list(selected):
        for c in unique:
            if c['id'] != chosen['id'] and shape(c) == shape(chosen) and c['text'] != chosen['text']:
                conflicts.append([chosen['id'], c['id']])
                if c not in selected: selected.append(c)
    return selected, {'query_terms':sorted(query), 'operand_terms':[sorted(p) for p in parts],
        'query_terms_missing':sorted(query-covered), 'removed_exact_duplicates':removed,
        'potential_conflicts_preserved':conflicts, 'target_k_exceeded_for_conflict':len(selected)>k,
        'abstain_without_context':True, 'fallback_extra_generation_calls':0,
        'limitation':'Lexical passage coverage is not fact extraction, arithmetic verification, entailment, or independent quality.'}


def numeric_proposal(context, specification, cfg, scope=None):
    """Review-only arithmetic from literal, period-bound source operands.

    Narrow supported grammar: ``NUMBER UNIT for PERIOD`` in indexed sentence
    passages containing the declared subject. The declaration supplies no values.
    Ambiguity/missing scope/negation fail closed. This never replaces an agent
    answer, adjudicates semantics, or authorizes release; reviewers judge whether
    the declared predicate and period actually answer the question.
    """
    if isinstance(specification,dict) and any(isinstance(o,dict) and 'predicate' in o for o in specification.get('operands',[])):
        from .facts import calculate
        bound=calculate(context,{'version':1,**specification},cfg,scope)
        return {**bound,'candidate_value':bound['value'],'inputs':bound['operands'],
                'origin':'deterministic_review_proposal_not_model_answer'}
    from decimal import Decimal, InvalidOperation
    from .evidence_contract import precheck
    import hashlib
    if not isinstance(specification, dict) or set(specification)-{'operation','operands'}:
        raise ValueError('Invalid calculation specification')
    operation=specification.get('operation');operands=specification.get('operands')
    if operation not in ('lookup','subtract','add') or not isinstance(operands,list) or len(operands)!=(1 if operation=='lookup' else 2):
        raise ValueError('Calculation requires explicit operation and operand count')
    for operand in operands:
        if not isinstance(operand,dict) or set(operand)!={'subject','unit','period'} or any(not isinstance(v,str) or not v.strip() or len(v)>120 for v in operand.values()):
            raise ValueError('Each operand requires subject, unit and period without values')
    if len({o['unit'].lower() for o in operands})!=1:
        raise ValueError('Operand units differ; no implicit conversion')
    eligible,screen=precheck('',context,cfg,None,scope)
    result={'status':'REVIEW','candidate_value':None,'semantic_approval':None,'operation':operation,
            'binding_assurance':'Legacy subject-proximity proposal only; use an explicit predicate contract for source-calculation answering',
            'inputs':[],'reasons':[],'origin':'deterministic_review_proposal_not_model_answer',
            'limitation':'Literal numeric binding and arithmetic are not independent semantic validation. No production answer or release is changed.'}
    if screen['unknown_applicability_ids']:
        result['reasons'].append('unknown_applicability');return result
    for operand in operands:
        hits=[]
        literal=lambda s:r'\s+'.join(re.escape(w) for w in s.split())
        pattern=re.compile(r'(?<![\w.,])([-+]?\d[\d,]*(?:\.\d+)?)\s+'+literal(operand['unit'])+r'\s+for\s+'+literal(operand['period'])+r'(?!\w)',re.I)
        for c in eligible:
            if c.get('chunk_strategy')!='sentences' or c.get('fragmented'):
                continue
            text=c['text']
            if re.search(r'\b(?:not|never|except|unless|however|excluded)\b',text,re.I):continue
            for match in pattern.finditer(text):
                if not re.search(r'(?<!\w)'+literal(operand['subject'])+r'(?!\w)',text[:match.start()],re.I):continue
                try:value=Decimal(match[1].replace(',',''))
                except InvalidOperation:continue
                if not value.is_finite():continue
                hits.append({'value':str(value),'id':c['id'],'document_id':c['document_id'],
                    'document_fingerprint':c.get('document_fingerprint'),'passage_sha256':hashlib.sha256(text.encode()).hexdigest(),
                    'quote':match[0],'subject':operand['subject'],'period':operand['period'],'unit':operand['unit'],
                    'quote_start':c['start']+match.start(),'quote_end':c['start']+match.end()})
        values={Decimal(h['value']) for h in hits}
        if len(values)!=1:
            result['reasons'].append('missing_or_ambiguous_operand');result['inputs'].append({'declaration':operand,'matches':hits});return result
        result['inputs'].append({'declaration':operand,'matches':hits,'value':str(next(iter(values)))})
    values=[Decimal(i['value']) for i in result['inputs']]
    value=values[0] if operation=='lookup' else values[0]-values[1] if operation=='subtract' else values[0]+values[1]
    result['candidate_value']=format(value,'f');result['reasons'].append('literal_calculation_requires_external_predicate_and_claim_review')
    return result
