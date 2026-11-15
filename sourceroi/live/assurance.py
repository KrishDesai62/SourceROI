"""Review-bound knowledge release assurance; never mutates authoritative labels.

A callback is a read-only integration boundary, not a sandbox for untrusted code.
Source sentences are candidate facts, not authoritative business interpretations.
"""
from copy import deepcopy
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import re
import time

from .data_ci import digest, evidence_coverage
from .grade import grade
from .ingest import scan_sources, load_benchmark, _extract, extract_document, MAX_EXTRACTED_CHARS
from .config import secure_path, read_config
from .provider import SYSTEM
from .diagnosis import diagnose
from . import db

EXIT_CODES = {'ACCEPT': 0, 'BLOCK': 3, 'REVIEW': 4, 'INCONCLUSIVE': 5}


def _inventory_in_process(cfg):
    docs, chunks = scan_sources(cfg)
    sources = {s['id']: s for s in cfg['sources']}
    return {d['id']: {'id': d['id'], 'hash': d['fingerprint'], 'source_id': d['source_id'],
        'passages': [p.strip() for p in re.split(r'(?<=[.!?])\s+|\n+', extract_document(secure_path(Path(cfg['_root']),d['path']),cfg)[:MAX_EXTRACTED_CHARS]) if p.strip() and terms(p)],
        'metadata': {k: sources[d['source_id']].get(k) for k in ('authority', 'effective_date', 'scope')},
        'source_metadata_hash':digest({k:v for k,v in sources[d['source_id']].items() if k!='path'})} for d in docs}, chunks


def configuration(cfg):
    # Hash configuration; never store credentials or external endpoint secrets.
    return digest({k: cfg.get(k) for k in ('model', 'agent', 'runner', 'settings')})


def terms(text):
    return set(re.findall(r'[a-z0-9]+', text.lower())) - {'the','a','an','is','of','to','and','for','what','how','within','may','must'}


def verify_snapshot(cfg):
    docs,_=scan_sources(cfg);tasks=load_benchmark(cfg)
    manifest={d['id']:d['fingerprint'] for d in docs}
    expected=digest({'manifest':manifest,'benchmark':tasks,'model':cfg.get('model'),'settings':cfg.get('settings'),
        'agent':cfg.get('agent'),'runner':cfg.get('runner','rag_chat'),
        'source_metadata':[{k:v for k,v in s.items() if k!='path'} for s in cfg['sources']]})
    path=Path(cfg['_root'])/'snapshot.json'
    if not path.exists():raise ValueError('Baseline must be a verified frozen snapshot')
    frozen=json.loads(path.read_text())
    if frozen.get('identity')!=expected or frozen.get('manifest')!=manifest:raise ValueError('Frozen snapshot tampered or stale')


def _propose_in_process(baseline, candidate, *, history=None, intent=None):
    verify_snapshot(baseline)
    old, _ = inventory(baseline); new, _ = inventory(candidate)
    tasks = load_benchmark(baseline)
    if digest(tasks) != digest(load_benchmark(candidate)):
        raise ValueError('Authoritative benchmark must remain unchanged; revisions belong in reviewed proposals')
    intent=intent or {}
    allowed={'expected_tasks','protected_tasks','declared_by','rationale'}
    if not isinstance(intent,dict) or set(intent)-allowed:raise ValueError('Invalid intent declaration')
    ids={t['id'] for t in tasks}
    for field in ('expected_tasks','protected_tasks'):
        if not isinstance(intent.get(field,[]),list) or any(not isinstance(t,str) or t not in ids for t in intent.get(field,[])):raise ValueError('Unknown intent task')
    expected_tasks=set(intent.get('expected_tasks',[]));protected_tasks=set(intent.get('protected_tasks',[]))|{t['id'] for t in tasks if t.get('behavior_constraint')=='protected'}
    if expected_tasks&protected_tasks:raise ValueError('Conflicting intent declaration')
    if intent and (not isinstance(intent.get('declared_by'),str) or not intent['declared_by'].strip() or not isinstance(intent.get('rationale'),str) or not intent['rationale'].strip()):raise ValueError('Intent requires declared_by and rationale')
    changes = []
    for ident in sorted(old.keys() | new.keys()):
        before, after = old.get(ident), new.get(ident)
        if before == after: continue
        removed = [] if before is None else list(before['passages'])
        added = [] if after is None else list(after['passages'])
        common = set(removed) & set(added)
        removed = [p for p in removed if p not in common]; added = [p for p in added if p not in common]
        changes.append({'document_id': ident, 'kind': 'added' if before is None else 'removed' if after is None else 'updated',
            'before_hash': before and before['hash'], 'after_hash': after and after['hash'],
            'removed_passages': removed, 'added_passages': added,
            'before_metadata': before and before['metadata'], 'after_metadata': after and after['metadata'],
            'facts': [{'id': digest([ident, p]), 'text': p, 'version': side} for side, ps in [('before',removed),('after',added)] for p in ps]})
    touched = {c['document_id'] for c in changes}
    impact = []; proposals = []
    for task in tasks:
        reasons = []
        refs = {e['document_id'] for e in task.get('evidence', [])}
        if refs & touched: reasons.append('annotated_evidence')
        if configuration(baseline)!=configuration(candidate): reasons.append('configuration_change')
        retrieved = set((history or {}).get(task['id'], []))
        metadata_changed={c['document_id'] for c in changes if c['kind']=='updated' and old[c['document_id']]['source_metadata_hash']!=new[c['document_id']]['source_metadata_hash']}
        if metadata_changed and (not refs or refs&metadata_changed or any(any(p.startswith(d+'#') or p==d for d in metadata_changed) for p in retrieved)):reasons.append('source_scope_or_authority_change')
        if any(any(p.startswith(d+'#') or p==d for d in touched) for p in retrieved): reasons.append('historical_retrieval')
        related = []
        for c in changes:
            text = ' '.join(c['removed_passages']+c['added_passages'])
            overlap = terms(task['question']) & terms(text)
            if len(overlap)>=2 or refs & {c['document_id']}:
                related.append(c['document_id'])
                if len(overlap)>=2 and 'topic_overlap' not in reasons: reasons.append('topic_overlap')
        # Classification adds explanation only; unknown tasks are never dropped.
        independent=bool(refs) and not refs&touched and not retrieved and not reasons and all(e['document_id'] in old and e['document_id'] in new and old[e['document_id']]==new[e['document_id']] and e['quote'] in extract_document(secure_path(Path(candidate['_root']),next(d['path'] for d in scan_sources(candidate)[0] if d['id']==e['document_id'])),candidate) for e in task.get('evidence',[]))
        dependency='confirmed_direct' if refs&touched or 'historical_retrieval' in reasons else 'potential' if reasons else 'unrelated_registered_evidence' if independent else 'unknown'
        impact.append({'dependency_class':dependency,'dependency_granularity':'document_or_lexical; not semantic fact causality','selection_status':'retain_for_full_release','task_id': task['id'], 'potentially_affected': bool(reasons) or dependency=='unknown', 'reasons': reasons,
                       'documents': sorted(set(related) | (refs&touched)), 'fact_ids':[f['id'] for c in changes if c['document_id'] in related for f in c['facts']], 'confidence':'heuristic', 'exhaustive':False})
        if not reasons: continue
        candidates = []
        for c in changes:
            if c['document_id'] not in related: continue
            # Conservative exact-substring edit; never inferred from agent output.
            for a in c['removed_passages']:
                for b in c['added_passages']:
                    if difflib.SequenceMatcher(None,a,b).ratio()<.65: continue
                    edits = [(a[i:j], b[k:l]) for op,i,j,k,l in difflib.SequenceMatcher(None,a,b).get_opcodes() if op!='equal']
                    na=re.findall(r'(?<!\w)-?\d+(?:\.\d+)?(?!\w)',a);nb=re.findall(r'(?<!\w)-?\d+(?:\.\d+)?(?!\w)',b)
                    numeric=[(x,y) for x,y in zip(na,nb) if x!=y] if len(na)==len(nb) else []
                    if len(numeric)==1 and re.sub(r'-?\d+(?:\.\d+)?','<value>',a)==re.sub(r'-?\d+(?:\.\d+)?','<value>',b):edits=numeric
                    if len(edits)==1 and all(re.fullmatch(r'[+-]?\d+(?:\.\d+)?',v) for v in edits[0]):
                        x,y=edits[0]
                        anchors=(terms(task['question'])-{'days','number','many','period','coverage','only','answer','with','customers','products'}) & terms(a)
                        linked=any(e['document_id']==c['document_id'] and e['quote'] in a for e in task.get('evidence',[]))
                        if not anchors or not linked:continue
                        candidates.append({'expected':y,'document_id':c['document_id'],'before_quote':a,'after_quote':b,'proposal_origin':'single_numeric_source_edit','independent_of_expected_label':True})
        if task.get('calculation_contract'):
            from .maintenance_evidence import value_proposal
            grounded=value_proposal(task,baseline,candidate)
            candidates=[grounded] if grounded else []
        unique = {p['expected'] for p in candidates}
        protected=task['id'] in protected_tasks or task.get('behavior_constraint')=='protected'
        scoped_change=any(c['before_metadata']!=c['after_metadata'] or old[c['document_id']]['source_metadata_hash']!=new[c['document_id']]['source_metadata_hash'] for c in changes if c['document_id'] in related and c['kind']=='updated')
        authority_known=all(new[d]['metadata'].get('authority') for d in related if d in new)
        classification='PROTECTED_UNCHANGED' if protected else 'AMBIGUOUS_REVIEW' if scoped_change else 'NO_SUPPORTED_CHANGE' if not candidates else 'PROPOSED_CHANGE' if task['id'] in expected_tasks and len(unique)==1 and not scoped_change and authority_known else 'AMBIGUOUS_REVIEW'
        proposals.append({'task_id':task['id'],'old_expected':task['expected'],
            'suggested_expected':next(iter(unique)) if classification=='PROPOSED_CHANGE' else None,
            'classification':classification,'candidate_facts':candidates,'confidence':'heuristic_source_match' if classification=='PROPOSED_CHANGE' else 'unresolved',
            'status':'pending', 'potentially_stale':bool(candidates), 'citations':candidates,
            'explanation':'Source-linked exact edit requires declared expected behavior and independent approval; protected expectations are preserved. Scope/authority changes remain reviewable.',
            'requires_review':True})
    # New facts get candidate questions, without invented authoritative answers.
    new_tests=[{'document_id':c['document_id'],'fact_id':f['id'], 'source_quote':f['text'],
                'question':f"What does {c['document_id']} state about {' '.join(sorted(terms(f['text']))[:5])}?",'expected':None,'status':'pending','reason':'Reviewer must supply a useful task and independent expectation'}
               for c in changes for f in c['facts'] if f['version']=='after']
    from .evidence_contract import has_fact_predicate
    conflicts=[];by_shape={}
    for document in new.values():
        for passage in document['passages']:
            if not re.search(r'\d',passage) or not has_fact_predicate(passage):continue
            shape=re.sub(r'\d+(?:\.\d+)?','<number>',passage.lower())
            for prev in by_shape.get(shape,[]):
                if prev['quote']!=passage:conflicts.append({'left':prev,'right':{'document_id':document['id'],'quote':passage},'status':'potential_numeric_conflict_requires_review'})
            if len(conflicts)>100:break
            by_shape.setdefault(shape,[]).append({'document_id':document['id'],'quote':passage})
    conflicted={entry[side]['document_id'] for entry in conflicts for side in ('left','right')}
    for proposal in proposals:
        if proposal['classification']=='PROPOSED_CHANGE' and any(c['document_id'] in conflicted for c in proposal['citations']):
            proposal.update(classification='AMBIGUOUS_REVIEW',suggested_expected=None,confidence='unresolved_conflict')
    from .maintenance_evidence import evidence_proposals
    evidence_updates=evidence_proposals(baseline,candidate,tasks)
    body={'evidence_proposals':evidence_updates,'version':1,'kind':'knowledge_change','baseline_sources':digest(old),'candidate_sources':digest(new),
        'baseline_configuration':configuration(baseline),'candidate_configuration':configuration(candidate),
        'test_set_version':digest(tasks),'potential_conflicts':conflicts[:100],'changes':changes,'impact':impact,'evaluation_proposals':proposals,
        'proposal_version':3,'candidate_tests':new_tests,'intent':{**intent,'status':'declared_requires_review' if intent else 'unknown','expected_tasks':sorted(expected_tasks),'protected_tasks':sorted(protected_tasks)},
        'limitations':['Sentence-level candidate facts; no semantic entailment proof.',
            'Historical retrieval and lexical overlap are not exhaustive; full suite is required for ACCEPT.',
            'Database/API records can be materialized through existing JSON/CSV adapters; live connectors are unsupported.']}
    body['id']=digest(body)
    return body


def validate_spec(spec):
    body={k:v for k,v in spec.items() if k!='id'}
    if spec.get('version')!=1 or spec.get('kind')!='knowledge_change' or digest(body)!=spec.get('id'):
        raise ValueError('Change specification hash/version mismatch')
    if not isinstance(spec.get('impact'),list) or not isinstance(spec.get('changes'),list) or not isinstance(spec.get('evaluation_proposals'),list):raise ValueError('Invalid change specification schema')


def review(spec, *, reviewer, expected_changes=None, protected_tasks=None, rejected_tasks=None, expected_evidence=None, evidence_updates=None, rationale=''):
    """Explicit human decision bound to immutable spec digest; no truth inferred from agent answers."""
    validate_spec(spec)
    if not isinstance(reviewer,str) or not reviewer.strip() or not isinstance(rationale,str) or not rationale.strip():
        raise ValueError('Named reviewer and rationale required')
    if rationale.lstrip().upper().startswith('DRAFT'):raise ValueError('Draft decisions require an explicit completed review rationale')
    changes=expected_changes if expected_changes is not None else {}; evidence=expected_evidence if expected_evidence is not None else {}; protected=protected_tasks if protected_tasks is not None else []; rejected=rejected_tasks if rejected_tasks is not None else []
    if not isinstance(changes,dict) or not isinstance(evidence,dict) or not isinstance(protected,list) or not isinstance(rejected,list):raise ValueError('Review fields must use expected dictionary/list types')
    if any(not isinstance(k,str) for k in list(changes)+list(evidence)+protected+rejected):raise ValueError('Review task IDs must be strings')
    ids={i['task_id'] for i in spec['impact']}
    if not set(changes)|set(protected)|set(rejected) <= ids: raise ValueError('Unknown reviewed task')
    if set(changes)&set(spec.get('intent',{}).get('protected_tasks',[])):raise ValueError('Cannot revise declared protected behavior; create a new reviewed intent specification')
    if set(changes)&set(protected) or set(changes)&set(rejected): raise ValueError('Conflicting review decisions')
    if any(not isinstance(v,str) or not v.strip() for v in changes.values()): raise ValueError('Expected answers must be nonempty strings')
    if not set(evidence)<=set(changes):raise ValueError('Replacement evidence requires an approved changed task')
    for refs in evidence.values():
        if not isinstance(refs,list) or not refs or any(not isinstance(r,dict) or not isinstance(r.get('document_id'),str) or not isinstance(r.get('quote'),str) or not r['quote'].strip() for r in refs):raise ValueError('Invalid replacement evidence')
    updates=evidence_updates or {}
    if not isinstance(updates,dict) or not set(updates)<=ids or set(updates)&(set(changes)|set(rejected)):raise ValueError('Evidence-only updates must preserve answers and cannot conflict with changed/rejected tasks')
    from .maintenance_evidence import validate_update
    for tid,decision in updates.items():validate_update(spec,tid,decision)
    body={'version':1,'spec_id':spec['id'],'reviewer':reviewer.strip(),'rationale':rationale,
          'expected_changes':changes,'expected_evidence':evidence,'protected_tasks':sorted(set(protected)), 'rejected_tasks':sorted(set(rejected)),
          'created_at':datetime.now(timezone.utc).isoformat()}
    if updates:body['evidence_updates']=updates
    return {**body,'id':digest(body)}


def validate_review(spec, approval):
    if approval is None:return
    if approval.get('spec_id')!=spec['id'] or approval.get('id')!=digest({k:v for k,v in approval.items() if k!='id'}):
        raise ValueError('Review is not bound to this exact specification')
    # Revalidate structure; a local named review is an assertion, not authenticated identity.
    review(spec,reviewer=approval.get('reviewer'),rationale=approval.get('rationale',''),
           expected_changes=approval.get('expected_changes'),protected_tasks=approval.get('protected_tasks'),rejected_tasks=approval.get('rejected_tasks'),expected_evidence=approval.get('expected_evidence'),evidence_updates=approval.get('evidence_updates'))


def markdown(report):
    lines=['# Knowledge change assurance', '', f"Verdict: **{report['verdict']}**", '', report['reason'], '',
           f"Specification: `{report['spec_id']}`", f"Calls: {report['execution']['calls']}", '',
           '| Task | Expected change | Before | After | Evidence loss |', '|---|---|---|---|---|']
    for r in report['tasks']:
        ident=r['task_id'].replace('|','\\|').replace('\n',' ')
        lines.append(f"| {ident} | {r['expected_change']} | {r['baseline_correct']} | {r['candidate_correct']} | {r['evidence_loss']} |")
    lines += ['', '## Source and review versions', '',json.dumps(report['versions'],indent=2), '',
              'Review: '+str((report.get('review') or {}).get('id','unapproved')), '',
              'Unresolved tasks: '+', '.join(report['unresolved_tasks']), '', '## Changed evidence', '']
    for c in report['specification']['changes']:
        lines += [c['document_id']+' ('+c['kind']+')',
            'Before: '+json.dumps(c['removed_passages'],ensure_ascii=False),
            'After: '+json.dumps(c['added_passages'],ensure_ascii=False), '']
    lines += ['## Required checks','',json.dumps(report.get('release_policy',{'name':'historical_legacy_exact'})),json.dumps(report.get('check_statuses',{})), 'Missing: '+', '.join(report.get('missing_checks',[])), 'Next: '+', '.join(report.get('next_actions',[]))]
    lines += ['## Measurement limits','', report.get('metric_scopes','Exact-answer checks and literal reference coverage; semantic/citation correctness unreviewed.'),
              'Execution: '+json.dumps(report['execution']),
              'No production changes applied. Candidate causes are hypotheses; full registered-suite acceptance does not establish universal safety.']
    return '\n'.join(lines)+'\n'


def validate_release_inputs(baseline,candidate,spec,approval=None):
    """Offline canonical source/review check shared by dispatch and release.

    No model calls, approvals or persistence are performed.
    """
    validate_spec(spec);validate_review(spec,approval)
    # Recompute from live inputs to detect TOCTOU edits to sources, labels or config.
    actual=propose(baseline,candidate)
    for k in ('baseline_sources','candidate_sources','test_set_version','baseline_configuration','candidate_configuration'):
        if actual[k]!=spec[k]:raise ValueError(f'Stale specification: {k}')
    if spec.get('changes')!=actual['changes'] or spec.get('potential_conflicts')!=actual['potential_conflicts']:raise ValueError('Specification source diff is not canonical')
    if (approval or {}).get('evidence_updates'):
        canonical={p['id'] for p in actual.get('evidence_proposals',[])}
        if any(d['proposal_id'] not in canonical for d in approval['evidence_updates'].values()):raise ValueError('Evidence proposal stale or not canonical for registered source versions')
    spec_impact={r['task_id']:r for r in spec['impact']}
    if len(spec_impact)!=len(spec['impact']) or set(spec_impact)!={r['task_id'] for r in actual['impact']}:raise ValueError('Impact task set is invalid')
    if any(r['potentially_affected'] and not spec_impact[r['task_id']]['potentially_affected'] for r in actual['impact']):raise ValueError('Required impact dependencies were removed')
    return actual


def execute(baseline,candidate,spec,*,approval=None,callback=None,max_calls=40,max_seconds=120,targeted=False,persist=True,policy=None,semantic_reviews=None,reviewers=()):
    """callback(cfg, tasks) -> standard evaluate_variant result. Labels never sent to callbacks."""
    from .release_policy import resolve,inspect,finalize,sample_for
    release_policy=resolve(candidate,policy)
    builtin=callback is None
    semantic_reviews=semantic_reviews or {}
    validate_spec(spec);validate_review(spec,approval)
    if type(max_calls) is not int or not 1<=max_calls<=400 or not 0<max_seconds<=900:raise ValueError('Invalid execution budget')
    validate_release_inputs(baseline,candidate,spec,approval)
    snapshot=Path(baseline['_root'])/'snapshot.json'
    old_docs,_=scan_sources(baseline)
    if not snapshot.exists() or json.loads(snapshot.read_text()).get('manifest')!={d['id']:d['fingerprint'] for d in old_docs}:
        raise ValueError('Baseline must be a verified frozen snapshot')
    budget=None
    start=time.monotonic(); all_tasks=load_benchmark(baseline)
    affected={r['task_id'] for r in spec['impact'] if r['potentially_affected']}
    selected=[t for t in all_tasks if t['id'] in affected] if targeted else all_tasks
    # Broad deterministic negative control in targeted mode; still cannot establish safety.
    controls=[t for t in all_tasks if t['id'] not in affected][:2] if targeted else []
    selected+=controls
    from .evaluation_inputs import maintained_tasks
    reviewed_tasks={t['id']:t for t in maintained_tasks(all_tasks,spec,approval)}
    expected=(approval or {}).get('expected_changes',{})
    reviewed=set(expected)|set((approval or {}).get('protected_tasks',[]))|set((approval or {}).get('evidence_updates',{}))
    unresolved=sorted(affected-reviewed)
    report={'kind':'knowledge_release','version':1,'spec_id':spec['id'],'specification':spec,
        'review':approval,'verdict':'INCONCLUSIVE','reason':'Execution incomplete', 'tasks':[],
        'execution':{'calls':0,'call_semantics':'Logical agent task executions; actual model calls separately recorded','max_calls':max_calls,'max_seconds':max_seconds,'targeted':targeted,
                     'selected_tasks':[t['id'] for t in selected], 'negative_controls':[t['id'] for t in controls],
                     'tasks_not_executed':len(all_tasks)-len(selected),'calls_avoided':2*(len(all_tasks)-len(selected))},
        'execution_identity':{'baseline_model':{k:baseline.get('model',{}).get(k) for k in ('name','seed','temperature','max_output_tokens','runtime')},'candidate_model':{k:candidate.get('model',{}).get(k) for k in ('name','seed','temperature','max_output_tokens','runtime')},'retrieval_settings':{k:v for k,v in candidate.get('settings',{}).items() if k in ('max_chunks','chunk_chars','chunk_strategy','table_evidence','overlap_chars','retrieval_policy','max_context_chars','retrieval_contract')},'prompt_version':digest(SYSTEM)},
        'versions':{k:spec[k] for k in ('baseline_sources','candidate_sources','test_set_version','baseline_configuration','candidate_configuration')},
        'reviewed_test_set_version':digest([spec['test_set_version'],expected]+([{'evidence_updates':(approval or {})['evidence_updates']}] if (approval or {}).get('evidence_updates') else [])),
        'unresolved_tasks':unresolved,'evaluation_maintenance':[dict(p,decision='approved' if p['task_id'] in expected else 'protected' if p['task_id'] in reviewed else 'rejected' if p['task_id'] in (approval or {}).get('rejected_tasks',[]) else 'pending', approved_expected=expected.get(p['task_id'])) for p in spec['evaluation_proposals']],'repairs':[], 'production_modified':False,
        'metric_limitations':{'semantic_correctness':None,'citation_correctness':None,'retrieval_quality':None,
             'contradictions':'Potential source conflicts require review; not semantically adjudicated.',
             'evaluation_cost_usd':None,'note':'Exact-match scores and literal annotated quote coverage are separate metrics.'}}
    rid=db.begin(candidate,'knowledge_release',[]) if persist else None
    if rid:report['run_id']=rid
    try:
        if not selected or 2*len(selected)>max_calls:raise ValueError('Empty selection or required calls exceed cap')
        _,a_chunks=inventory(baseline);_,b_chunks=inventory(candidate)
        if callback is None:
            from .engine import evaluate_variant
            from .validation import Budget
            # This workflow permits local inference only, regardless of other supported runners.
            if any(not c.get('model',{}).get('local_only') or c.get('runner','rag_chat')!='rag_chat' for c in (baseline,candidate)):
                raise ValueError('Use local-only model or an explicit trusted local callback')
            budget=Budget({**candidate.get('settings',{}),'max_model_calls_per_run':max_calls,'max_run_seconds':max_seconds})
            callback=lambda cfg,ts:evaluate_variant({**cfg,'_experiment_budget':budget,'settings':{**cfg.get('settings',{}),'release_policy':{'version':1,'name':release_policy['name']}}},ts,a_chunks if cfg is baseline else b_chunks,[])
            inputs=selected
        else:
            # Do not let evaluated agent produce its own labels.
            inputs=[{k:v for k,v in t.items() if k in ('id','question','answer_contract','evidence_contract','scope','requires_grounding','calculation_contract','calculation_authorization')} for t in selected]
        before=callback(baseline,deepcopy(inputs));report['execution']['calls']+=len(selected)
        if time.monotonic()-start>max_seconds:raise TimeoutError('Deadline exceeded after baseline')
        after=callback(candidate,deepcopy(inputs));report['execution']['calls']+=len(selected)
        if time.monotonic()-start>max_seconds:raise TimeoutError('Deadline exceeded after candidate')
        fresh=propose(read_config(baseline['_root']),
                      read_config(candidate['_root']))
        if any(fresh[k]!=spec[k] for k in ('baseline_sources','candidate_sources','test_set_version','baseline_configuration','candidate_configuration')):
            raise ValueError('Inputs changed during evaluation')
        report['baseline']=before;report['candidate']=after
        for result in (before,after):
            for row in result['tasks']:
                if not row.get('response_complete',True):raise ValueError('Incomplete agent response')
                if 'answer' not in row and isinstance(row.get('actual'),str):row['answer']=row['actual']
                if not isinstance(row.get('answer'),str) or not isinstance(row.get('retrieved_chunk_ids'),list):raise ValueError('Unsupported agent result schema')
        a={r['id']:r for r in before['tasks']};b={r['id']:r for r in after['tasks']}
        required={t['id'] for t in selected}
        if len(before['tasks'])!=len(selected) or len(after['tasks'])!=len(selected) or set(a)!=required or set(b)!=required:raise ValueError('Adapter returned incomplete or unexpected task results')
        blocking=[]
        for t in selected:
            ident=t['id']; revised=deepcopy(reviewed_tasks[ident])
            from .answer_contract import check as check_answer
            old_format,old_reason=check_answer(a[ident]['answer'] if a[ident]['answer']=='INSUFFICIENT_EVIDENCE' else a[ident].get('raw_answer',a[ident]['answer']),t.get('answer_contract'))
            new_format,new_reason=check_answer(b[ident]['answer'] if b[ident]['answer']=='INSUFFICIENT_EVIDENCE' else b[ident].get('raw_answer',b[ident]['answer']),t.get('answer_contract'))
            old_format=old_format and a[ident].get('answer_contract_valid',True)
            new_format=new_format and b[ident].get('answer_contract_valid',True)
            a[ident]['answer_contract_valid']=old_format;b[ident]['answer_contract_valid']=new_format
            old=grade(a[ident]['answer'],t) and old_format;new=grade(b[ident]['answer'],revised) and new_format
            ac=evidence_coverage(t,a[ident],a_chunks);bc=evidence_coverage(revised,b[ident],b_chunks)
            loss=ident not in expected and ac is not None and bc is not None and bc<ac
            fail=(not new or loss) and ident not in unresolved
            fail=fail or (ident in expected and (not new or (bc is not None and bc<1)))
            if fail:blocking.append(ident)
            sample=sample_for(revised,b[ident],b_chunks,candidate,spec['candidate_sources'])
            checks=inspect(revised,b[ident],b_chunks,candidate,spec['candidate_sources'],review=semantic_reviews.get(digest(sample)),reviewers=reviewers,builtin=builtin)
            docs=next(i['documents'] for i in spec['impact'] if i['task_id']==ident)
            report['tasks'].append({**({'calculation_contract':t['calculation_contract']} if t.get('calculation_contract') else {}),'task_id':ident,'expected_change':ident in expected,'baseline_correct':old,
                'candidate_correct':new,'answer_contract':t.get('answer_contract'),'answer_contract_valid':new_format,'answer_contract_reason':new_reason,'requires_grounding':t.get('requires_grounding',False),'grounding_checks':checks,'baseline_evidence_coverage':ac,'candidate_evidence_coverage':bc,'evidence_loss':loss,
                'candidate_causes':docs[:3],'diagnosis':diagnose(revised,b[ident],b_chunks,candidate) if not new or loss else None,'cause_status':'hypothesis; controlled repair required'})
        report['blocking_tasks']=blocking
        report['release_metrics']={'baseline_exact_accuracy':sum(t['baseline_correct'] for t in report['tasks'])/len(selected),'approved_candidate_exact_accuracy':sum(t['candidate_correct'] for t in report['tasks'])/len(selected),'semantic_correctness':None,'citation_correctness':None,'evidence_loss_tasks':sum(t['evidence_loss'] for t in report['tasks'])}
        report['metric_scopes']='Raw engine metrics use original benchmark labels; release_metrics and task results apply only explicit approved revisions. Semantic and citation correctness remain unreviewed.'
        drift=spec['baseline_configuration']!=spec['candidate_configuration']
        if blocking:report.update(verdict='BLOCK',reason='Confirmed expectation or protected-evidence failure on evaluated tasks')
        elif len(selected)<len(all_tasks):report.update(verdict='INCONCLUSIVE',reason='Targeted checks passed; broader tasks remain unexecuted')
        elif spec.get('potential_conflicts'):report.update(verdict='REVIEW',reason='Potential numerical source contradictions remain unresolved')
        elif drift:report.update(verdict='REVIEW',reason='Model/prompt/retrieval configuration changed; source-only attribution is confounded')
        elif approval is None or unresolved:report.update(verdict='REVIEW',reason='Knowledge intent is unapproved or impacted behaviors remain unresolved')
        elif any(r['candidate_evidence_coverage'] is None or r['candidate_evidence_coverage']<1 for r in report['tasks']):report.update(verdict='REVIEW',reason='Some evaluated behaviors lack independently reviewed evidence references')
        elif set(expected)-set((approval or {}).get('expected_evidence',{})):report.update(verdict='REVIEW',reason='Approved answers passed; replacement evidence citations and applicability require independent review')
        else:report.update(verdict='ACCEPT',reason='Full registered suite passed approved protected expectations and measured evidence checks; scope is this suite only')
    except Exception as exc:
        report.update(verdict='INCONCLUSIVE',reason=f'Execution failed ({type(exc).__name__}); inspect local configuration or adapter without exporting sensitive exception text')
    finally:
        from .maintenance import counters
        report['maintenance']=counters(spec,approval)
        finalize(report,release_policy)
        report['execution']['model_generation_calls']=budget.calls if budget is not None else None
        report['execution']['wall_seconds']=round(time.monotonic()-start,6)
        report['source_recommendations']=source_value(report)
        if rid:db.finish(candidate,rid,report)
    return report


def save_proposal(cfg,spec):
    validate_spec(spec)
    rid=db.begin(cfg,'knowledge_change',[]);db.finish(cfg,rid,spec)
    return rid


def save_review(cfg,spec,approval):
    validate_spec(spec);validate_review(spec,approval)
    rid=db.begin(cfg,'knowledge_review',[])
    db.finish(cfg,rid,{'kind':'knowledge_review','spec_id':spec['id'],'review':approval})
    return rid


def timeline(cfg):
    with db.connect(cfg) as conn:
        rows=conn.execute("SELECT id,mode,created_at,report FROM runs WHERE mode IN ('knowledge_release','knowledge_change','knowledge_review','knowledge_decision') ORDER BY created_at,id").fetchall()
    events=[]
    for row in rows:
        if not row['report']:continue
        report=json.loads(row['report']);spec=report.get('specification',report if row['mode']=='knowledge_change' else {})
        events.append({'run_id':row['id'],'kind':row['mode'],'at':row['created_at'],
            'spec_id':report.get('spec_id',spec.get('id')),'versions':report.get('versions'),
            'verdict':report.get('verdict'),'release_policy':report.get('release_policy'),'check_statuses':report.get('check_statuses'),'tasks':report.get('tasks'),'fact_changes':spec.get('changes'),
            'review':report.get('review'),'repairs':report.get('repairs'),
            'recommendations':report.get('recommendations'),'recommended_experiment':report.get('recommended_experiment')})
    return events


def verify_repair(baseline,candidate,spec,repaired,repair_spec,*,approval,repair_approval,callback=None,max_calls=80,max_seconds=120):
    """Joint controlled intervention. Explicitly reviewed repair expectations; no source mutation."""
    if configuration(candidate)!=configuration(repaired):raise ValueError('Repair changes agent configuration; source attribution is confounded')
    start=time.monotonic()
    before=execute(baseline,candidate,spec,approval=approval,callback=callback,max_calls=max_calls,max_seconds=max_seconds)
    remaining=max_calls-before['execution']['calls'];seconds=max_seconds-(time.monotonic()-start)
    if remaining<1 or seconds<=0:
        return {'kind':'knowledge_repair','verdict':'INCONCLUSIVE','reason':'Shared repair budget exhausted','before':before,'automatically_applied':False}
    after=execute(baseline,repaired,repair_spec,approval=repair_approval,callback=callback,max_calls=remaining,max_seconds=seconds)
    restored=before['verdict']=='BLOCK' and after['verdict']=='ACCEPT'
    return {'kind':'knowledge_repair','verdict':'ACCEPT' if restored else 'INCONCLUSIVE','before':before,'after':after,
        'restored_registered_suite':restored,'calls':before['execution']['calls']+after['execution']['calls'],
        'automatically_applied':False,'causal_limit':'Joint intervention supports this configuration only; individual changed facts are not uniquely causal.'}


def source_value(report):
    """Task-specific review recommendations, never removal from unchanged average accuracy."""
    rows=[]
    for c in report['specification']['changes']:
        impacted=[t for t in report['tasks'] if c['document_id'] in t['candidate_causes']]
        harmful=any(not t['candidate_correct'] or t['evidence_loss'] for t in impacted)
        rows.append({'document_id':c['document_id'],'before_version':c['before_hash'],'after_version':c['after_hash'],
            'tasks':[t['task_id'] for t in impacted], 'recommendation':'REVIEW' if harmful or not impacted else 'KEEP',
            'reason':'Observed failure/support change needs controlled ablation' if harmful else 'No removal justified by this version comparison',
            'marginal_contribution':None,'limitation':'Use existing dataset/document ablations to measure controlled marginal value; version comparison is observational.'})
    return rows


def inventory(cfg):
    from .analysis_boundary import active,source
    if active():return _inventory_in_process(cfg)
    result=source('inventory',cfg)
    if not isinstance(result,list) or len(result)!=2:raise ValueError('Invalid inventory result')
    return result[0],result[1]


def propose(baseline,candidate,*,history=None,intent=None):
    from .analysis_boundary import active,plan
    if active():return _propose_in_process(baseline,candidate,history=history,intent=intent)
    return plan(baseline,candidate,history,intent)
