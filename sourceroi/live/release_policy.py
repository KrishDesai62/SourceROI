"""Versioned release requirements; literal checks never establish semantic truth."""
from copy import deepcopy
from .data_ci import digest,evidence_coverage
from .reliability_review import evaluate


def resolve(cfg,policy=None):
    configured=cfg.get('settings',{}).get('release_policy','legacy_exact')
    value=policy if policy is not None else configured
    if isinstance(value,str):value={'version':1,'name':value}
    if not isinstance(value,dict) or set(value)-{'version','name'} or value.get('version')!=1 or value.get('name') not in ('legacy_exact','strict_grounded'):
        raise ValueError('Release policy must be version 1: legacy_exact or strict_grounded')
    configured_name=configured if isinstance(configured,str) else configured.get('name')
    if configured_name=='strict_grounded' and value['name']!='strict_grounded':raise ValueError('Configured strict grounded policy cannot be downgraded')
    return {**value,'required_checks':['execution','intent_approval','exact_answer','reference_coverage']+(['citation_integrity','scope_applicability','version_provenance','semantic_review','evidence_relevance','contradictory_evidence'] if value['name']=='strict_grounded' else [])}


def citation_required(cfg,task=None):
    return resolve(cfg)['name']=='strict_grounded' or (task or {}).get('requires_grounding',False)


def sample_for(task,row,chunks,cfg,source_version):
    sources={s['id']:s for s in cfg['sources']};known={c['id']:c for c in chunks}
    context=[]
    for cid in row['retrieved_chunk_ids']:
        if cid not in known:continue
        c=known[cid];source=sources[c['source_id']]
        context.append({**c,**{k:source[k] for k in ('jurisdiction','effective_from','effective_to','policy_scope','authority') if k in source}})
    sample={'question':task['question'],'answer':row.get('answer',row.get('actual')),
        'citations':row.get('citations',[]),'context':context,'scope':task.get('scope',{}),
        'source_version':source_version,'response_contract_valid':row.get('json_format_valid',True)}
    if task.get('answer_contract'):
        sample.update(answer_contract=task['answer_contract'],answer_contract_valid=row.get('answer_contract_valid'),raw_answer=row.get('raw_answer'))
    return sample


def inspect(task,row,chunks,cfg,source_version,*,review=None,reviewers=(),builtin=False):
    sample=sample_for(task,row,chunks,cfg,source_version)
    judged=evaluate(sample,review,allowed_reviewers=reviewers)
    known={c['id']:c for c in sample['context']};cites=sample['citations']
    cited=[known[c] for c in cites if c in known]
    coverage=evidence_coverage(task,{'retrieved_chunk_ids':[c['id'] for c in cited]},cited)
    invalid=list(dict.fromkeys(judged['deterministic']['invalid_citations']+row.get('invalid_citations',[])))
    if row.get('json_format_valid',True) is not True:ci='BLOCK';reason='Malformed grounded response contract'
    elif invalid:ci='BLOCK';reason='Citations were not supplied by this knowledge version/retrieval'
    elif not cites:ci='BLOCK';reason='Required supporting citations are missing'
    elif coverage is not None and coverage<1:ci='BLOCK';reason='Cited passages do not cover required annotated support'
    elif coverage is None:ci='REVIEW';reason='No reviewed evidence requirements establish citation support'
    else:ci='PASS';reason='Cited IDs and literal annotated support verified; not semantic entailment'
    applicability=judged['deterministic']['explicit_applicability']
    if any(c['applicable'] is False for c in applicability):scope='BLOCK'
    elif task.get('scope') and (not applicability or any(c['applicable'] is None for c in applicability)):scope='REVIEW'
    else:scope='PASS'
    if builtin:version='PASS'
    else:
        from .ingest import scan_sources
        expected={d['id']:d['fingerprint'] for d in scan_sources(cfg)[0]}
        identity=cfg.get('agent',{}).get('execution_identity')
        version='PASS' if row.get('knowledge_manifest')==expected and row.get('knowledge_version')==digest(expected) and (identity is None or identity==row.get('execution_identity')) else 'INCONCLUSIVE'
    if judged['review_status']!='complete':semantic='REVIEW'
    elif not judged['semantic_correctness'] or not judged['citation_correctness'] or not judged['scope_appropriate'] or judged['uses_outdated_fact']:semantic='BLOCK'
    else:semantic='PASS'
    from .evidence_contract import precheck
    _,screen=precheck(task['question'],sample['context'],cfg,task.get('evidence_contract'),task.get('scope'))
    abstained=sample['answer']=='INSUFFICIENT_EVIDENCE'
    relevance='BLOCK' if screen['missing_declared_alias_groups'] and not abstained else 'PASS' if judged['review_status']=='complete' and judged['citation_correctness'] else 'REVIEW'
    numeric_status='REVIEW';numeric_binding=None
    if task.get('calculation_contract') and not abstained:
        from .facts import authorized,calculate
        if authorized(task['question'],task.get('scope'),task['calculation_contract'],task.get('calculation_authorization'),cfg.get('settings',{}).get('calculation_reviewers',[])):
            numeric_binding=calculate(cited,task['calculation_contract'],cfg,task.get('scope'))
            state=numeric_binding['binding_status']
            if state=='supported_grammar':
                from decimal import Decimal,InvalidOperation
                try:
                    matches=(sample['answer']==numeric_binding['value'] if numeric_binding['value'] in ('true','false')
                             else Decimal(sample['answer'])==Decimal(numeric_binding['value']))
                except (InvalidOperation,TypeError,ValueError):matches=False
                numeric_status='PASS' if matches else 'BLOCK'
            elif state=='invalid_provenance':numeric_status='INCONCLUSIVE'
            elif state in ('missing','out_of_scope'):numeric_status='BLOCK'
            if numeric_binding['binding_status']=='supported_grammar' and screen['missing_declared_alias_groups']:
                from .facts import unresolved_table_subjects
                if not unresolved_table_subjects(screen['missing_declared_alias_groups'],numeric_binding):
                    relevance='PASS' if judged['review_status']=='complete' and judged['citation_correctness'] else 'REVIEW'
        # This is a declared numerical contract check, not semantic approval.
    contradiction='REVIEW' if screen['potential_conflicts'] else 'PASS'
    if abstained and not cites and not invalid:
        ci='REVIEW';reason='No factual claim/citation generated; appropriateness of abstention still requires review'
    return {'numeric_evidence_status':numeric_status,'numeric_binding':numeric_binding,'sample':sample,'evidence_screen':screen,'relevance_status':relevance,'contradiction_status':contradiction,'claim_entailment':judged.get('groundedness'),'sample_key':digest(sample),'citation_status':ci,'citation_reason':reason,
        'cited_reference_coverage':coverage,'invalid_citations':invalid,'scope_status':scope,
        'version_status':version,'semantic_status':semantic,'review':judged,
        'scope_requested':bool(task.get('scope')),'scope_reason':'Explicit metadata evaluated against task scope' if task.get('scope') else 'No explicit task scope requested; absence of a mismatch is not date/jurisdiction validation',
        'source_ids':sorted({c['source_id'] for c in cited})}


def finalize(report,policy):
    report['release_policy']={**policy,'sha256':digest(policy)}
    if not report.get('tasks'):
        report['check_statuses']={'execution':'INCONCLUSIVE'};report['missing_checks']=policy['required_checks'];report['blocking_reasons']=[]
        report['next_actions']=['Complete the bounded evaluation'];return
    rows=report['tasks']
    def aggregate(values):
        return next((state for state in ('BLOCK','INCONCLUSIVE','REVIEW') if state in values),'PASS')
    statuses={'execution':'PASS' if len(rows)==len(report['execution']['selected_tasks']) and not report['execution']['tasks_not_executed'] and report['verdict']!='INCONCLUSIVE' else 'INCONCLUSIVE',
        'intent_approval':'PASS' if report.get('review') is not None and not report['unresolved_tasks'] else 'REVIEW',
        'exact_answer':'PASS' if all(r['candidate_correct'] for r in rows) else 'BLOCK',
        'reference_coverage':'PASS' if all(r['candidate_evidence_coverage']==1 for r in rows) else 'REVIEW',
        'citation_integrity':aggregate([r['grounding_checks']['citation_status'] for r in rows]),
        'scope_applicability':aggregate([r['grounding_checks']['scope_status'] for r in rows]),
        'version_provenance':aggregate([r['grounding_checks']['version_status'] for r in rows]),
        'semantic_review':aggregate([r['grounding_checks']['semantic_status'] for r in rows]),
        'evidence_relevance':aggregate([r['grounding_checks']['relevance_status'] for r in rows]),
        'contradictory_evidence':aggregate([r['grounding_checks']['contradiction_status'] for r in rows]),
        'answer_format':'PASS' if all(r.get('answer_contract_valid',True) for r in rows) else 'BLOCK'}
    # Unknown intent is not a confirmed changed-answer regression.
    if report['unresolved_tasks'] and statuses['exact_answer']=='BLOCK' and report['verdict']=='REVIEW':statuses['exact_answer']='REVIEW'
    required=set(policy['required_checks'])
    if any(r.get('answer_contract') for r in rows):required.add('answer_format')
    if any(r.get('calculation_contract') for r in rows):
        required.add('numeric_evidence')
        statuses['numeric_evidence']=aggregate([r['grounding_checks'].get('numeric_evidence_status','REVIEW') for r in rows if r.get('calculation_contract')])
    if any(r.get('requires_grounding') for r in rows):required.update(['citation_integrity','scope_applicability','version_provenance','semantic_review','evidence_relevance','contradictory_evidence'])
    report['check_statuses']=statuses;report['required_checks']=sorted(required)
    report['missing_checks']=[k for k in required if statuses[k] in ('REVIEW','INCONCLUSIVE')]
    report['blocking_reasons']=[k for k in required if statuses[k]=='BLOCK']
    if report['blocking_reasons']:
        report.update(verdict='BLOCK',reason='Required checks failed: '+', '.join(sorted(report['blocking_reasons'])))
    elif report['verdict']!='BLOCK' and any(statuses[k]=='INCONCLUSIVE' for k in required):
        report.update(verdict='INCONCLUSIVE',reason='Required execution/provenance checks are unavailable or incomplete')
    elif report['verdict']=='ACCEPT' and report['missing_checks']:
        report.update(verdict='REVIEW',reason='Required review remains unresolved: '+', '.join(sorted(report['missing_checks'])))
    report['approval_scope']='Registered '+policy['name']+' policy only; exact-answer success is not independent grounding proof'
    report['next_actions']=['Review '+k for k in report['missing_checks']]+['Repair '+k for k in report['blocking_reasons']]
