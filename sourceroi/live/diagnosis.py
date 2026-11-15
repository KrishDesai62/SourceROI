"""Post-failure diagnostics using supplied reference evidence; no speculative purchases."""
from .retrieve import search


def _diagnose_in_process(task, row, chunks, cfg=None, *, calculation=None):
    if row.get('answer_origin')=='source_calculation':
        binding=row.get('calculation',{}).get('binding_status','unavailable')
        return {'task_id':task['id'],'classification':'source_calculation_abstention' if row.get('actual')=='INSUFFICIENT_EVIDENCE' else 'calculation_or_label_mismatch',
                'reason':'Inspect declared operation, bound source operands, authorization and labels; binding state: '+binding,
                'certainty':'mechanism_observed_not_semantic_proof','model_generation_executed':False,
                'calculation':row.get('calculation'),'limitation':'A deterministic answer mismatch is not a model-generation failure or independently proven wrong label.'}
    guard=row.get('grounding_precheck') or {}
    if row.get('answer_origin')=='evidence_precheck' and guard.get('abstain'):
        return {'task_id':task['id'],'classification':'declared_evidence_precheck_abstention',
            'reason':'Software abstention before generation: '+', '.join(guard.get('reasons',[])),
            'certainty':'mechanism_observed_not_semantic_proof','model_generation_executed':False,
            'limitation':'Inspect alias completeness, scope metadata and potential conflicts; necessary evidence screening is not universal semantic truth.'}
    refs = task.get('evidence', [])
    if not refs:
        return {'task_id':task['id'],'classification':'inconclusive','reason':'No independently supplied evidence requirements', 'certainty':'unknown'}
    selected = {c['id'] for c in chunks if c['id'] in row.get('retrieved_chunk_ids', [])}
    ranked = {c['id'] for c in search(task['question'],chunks,k=100)}
    corpus_hits = [e for e in refs if any(c['document_id']==e['document_id'] and e['quote'] in c['text'] for c in chunks)]
    context_hits = [e for e in refs if any(c['id'] in selected and c['document_id']==e['document_id'] and e['quote'] in c['text'] for c in chunks)]
    ranked_hits = [e for e in refs if any(c['id'] in ranked and c['document_id']==e['document_id'] and e['quote'] in c['text'] for c in chunks)]
    fulltext_hits = None
    if cfg is not None:
        from pathlib import Path
        from .config import secure_path
        from .ingest import scan_sources,_extract,extract_document
        corpus_text={d['id']:extract_document(secure_path(Path(cfg['_root']),d['path']),cfg) for d in scan_sources(cfg,include_text=False)[0]}
        fulltext_hits=[e for e in refs if e['document_id'] in corpus_text and e['quote'] in corpus_text[e['document_id']]]
    signals = (row.get('selection') or {}).get('uncertainty_signals', [])
    if not corpus_hits and fulltext_hits:
        category,reason='present_not_retrieved','Reference text exists in original documents but is absent from chunks; inspect chunk boundaries, extraction limits or indexing'
    elif not corpus_hits:
        category,reason='reference_evidence_absent','Published reference quotes absent from current chunks; equivalent evidence elsewhere is not ruled out'
    elif len(context_hits)==len(refs):
        category,reason='generation_or_scoring_failure','All reference quotes were supplied; ignoring/misinterpretation, exact-match ambiguity, or generation error needs review'
    elif ranked_hits and len(context_hits)<len(ranked_hits):
        category,reason='retrieved_then_filtered','Reference evidence occurs in ranked candidates but is not fully supplied after selection'
    else:
        category,reason='present_not_retrieved','Reference evidence occurs in corpus but is not fully retrieved; chunk boundaries may also contribute'
    if 'potential_conflict_preserved' in signals or 'temporal_scope_requires_review' in signals:
        reason += '; possible conflict/temporal signals require independent review'
    proposal = {}
    if calculation is not None:
        if cfg is None:raise ValueError('Calculation diagnosis requires source configuration')
        from .evidence import numeric_proposal
        proposal['numeric_evidence_proposal'] = numeric_proposal([c for c in chunks if c['id'] in selected],calculation,cfg,task.get('scope'))
    return {**proposal,'task_id':task['id'],'classification':category,'reason':reason,'certainty':'diagnostic_hypothesis',
            'full_document_reference_hits':len(fulltext_hits) if fulltext_hits is not None else None,
            'corpus_reference_hits':len(corpus_hits),'ranked_reference_hits':len(ranked_hits),'supplied_reference_hits':len(context_hits),
            'limitation':'Reference annotations may be incomplete. This does not establish universal missing information or causal importance.'}


def test_source_addition(cfg, tasks, chunks, excluded_sources, candidate_source, budget):
    from .engine import evaluate_variant,compare_variants
    if candidate_source not in {s['id'] for s in cfg['sources']} or candidate_source not in excluded_sources:
        raise ValueError('Candidate must be an available, registered source excluded from baseline')
    local={**cfg,'_experiment_budget':budget}
    before=evaluate_variant(local,tasks,chunks,excluded_sources)
    after=evaluate_variant(local,tasks,chunks,[s for s in excluded_sources if s!=candidate_source])
    return {'candidate_source':candidate_source,'baseline':before,'with_candidate':after,
            'comparison':compare_variants(before,after),'automatically_purchased':False,
            'note':'Controlled available-source addition on these tasks, not a purchase recommendation or universal causal claim.'}


def diagnose(task,row,chunks,cfg=None,*,calculation=None):
    from .analysis_boundary import active,source,call
    if active():return _diagnose_in_process(task,row,chunks,cfg,calculation=calculation)
    if cfg is None:return call('diagnose',task=task,row=row,chunks=chunks,cfg=None,calculation=calculation)
    return source('diagnose',cfg,task=task,row=row,chunks=chunks,calculation=calculation)
