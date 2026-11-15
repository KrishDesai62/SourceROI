"""Analyze frozen real IRS outputs and explicit no-inference stress controls."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace/.deps'))
from tools.validate_real_world_e2e import ART,BASE,dump
from sourceroi.live import assurance as a
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.data_ci import digest,evidence_coverage
from sourceroi.live.answer_contract import check
from sourceroi.live.grade import grade
from sourceroi.live.release_policy import inspect,resolve,finalize
from sourceroi.live.policies import select_context
from sourceroi.live.evidence_contract import precheck
from sourceroi.live.diagnosis import diagnose


def revised(task,annotation,stage):
    result=deepcopy(task);result['expected']=annotation['expected_'+stage];result['evidence']=annotation['evidence_'+stage]
    return result


def conventional(before,after,release,annotations):
    start=time.perf_counter();a.verify_snapshot(before)
    if digest(load_benchmark(before))!=digest(load_benchmark(after)):raise ValueError('Benchmark drift')
    docs,chunks=scan_sources(after);manifest={d['id']:d['fingerprint'] for d in docs}
    rows={r['id']:r for r in release['candidate']['tasks']};result=[]
    for task in load_benchmark(after):
        t=revised(task,annotations[task['id']],'after');row=rows[t['id']]
        fmt,_=check(row['answer'] if row['answer']=='INSUFFICIENT_EVIDENCE' else row.get('raw_answer',row['answer']),t.get('answer_contract'))
        correct=grade(row['answer'],t) and fmt and row.get('response_complete',True)
        checks=inspect(t,row,chunks,after,release['versions']['candidate_sources'],builtin=False)
        reasons=[]
        if not correct:reasons.append('registered_answer')
        if not fmt:reasons.append('answer_format')
        if checks['citation_status']=='BLOCK':reasons.append('citation_integrity')
        if checks['scope_status']=='BLOCK':reasons.append('scope_applicability')
        if checks['relevance_status']=='BLOCK':reasons.append('necessary_evidence')
        incomplete=row.get('knowledge_manifest')!=manifest or checks['version_status']=='INCONCLUSIVE'
        verdict='BLOCK' if reasons else 'INCONCLUSIVE' if incomplete else 'REVIEW' # No independent semantics supplied to either workflow.
        result.append({'task_id':t['id'],'candidate_correct':correct,'verdict':verdict,'reasons':reasons,'shared_checks':checks})
    verdict='BLOCK' if any(r['verdict']=='BLOCK' for r in result) else 'INCONCLUSIVE' if any(r['verdict']=='INCONCLUSIVE' for r in result) else 'REVIEW'
    return {'verdict':verdict,'tasks':result,'wall_ms':1000*(time.perf_counter()-start),
        'conditions':'Same labels, outputs, source versions, format/citation/scope/relevance/provenance and missing independent-review requirements. Shared deterministic primitives; not independent checker validation.'}


def stress_controls(after,release,tasks):
    _,chunks=scan_sources(after);saved={r['id']:r for r in release['candidate']['tasks']}
    base=deepcopy(tasks['business']);base['expected']='70';base['evidence']=[{'document_id':'current::CURRENT notice.pdf','quote':'2025 is 70'}]
    observed=deepcopy(saved['business']);controls=[]
    def inspect_case(name,t,row,context=None,origin='controlled mutation of an observed output; no new model generation'):
        available=chunks if context is None else context
        c=inspect(t,row,available,after,release['versions']['candidate_sources'],builtin=False)
        fmt,reason=check(row['answer'] if row['answer']=='INSUFFICIENT_EVIDENCE' else row.get('raw_answer',row['answer']),t.get('answer_contract'))
        correct=grade(row['answer'],t) and fmt
        block=not correct or c['citation_status']=='BLOCK' or c['scope_status']=='BLOCK' or c['relevance_status']=='BLOCK'
        verdict='BLOCK' if block else 'INCONCLUSIVE' if c['version_status']=='INCONCLUSIVE' else 'REVIEW'
        controls.append({'case':name,'origin':origin,'check_only_verdict':verdict,'registered_correct':correct,'answer_format_valid':fmt,
            'format_reason':reason,'checks':c,'actual_new_model_calls':0})
    # Actual misleading-value case, not an injected model answer.
    char=deepcopy(tasks['charity']);char['expected']='14'
    inspect_case('observed_charity_21_with_valid_retrieved_ids',char,deepcopy(saved['charity']),origin='observed real generation')
    invalid=deepcopy(observed);invalid['answer']='70 days';invalid['raw_answer']='70 days';invalid['actual']='70 days';invalid['answer_contract_valid']=False
    inspect_case('correct_value_invalid_numeric_format',base,invalid)
    wrong_cite=deepcopy(observed)
    irrelevant=next(c for c in chunks if c['id'] not in observed['retrieved_chunk_ids'])
    wrong_cite['citations']=[irrelevant['id']]
    inspect_case('citation_exists_but_was_not_retrieved',base,wrong_cite)
    stale=deepcopy(observed);stale['knowledge_manifest']={'current::CURRENT notice.pdf':'0'*64}
    inspect_case('stale_manifest_attestation',base,stale)
    old_date=deepcopy(base);old_date['scope']['as_of']='2024-06-01'
    inspect_case('2025_source_for_2024_effective_date',old_date,deepcopy(observed))
    wrong_scope=deepcopy(base);wrong_scope['scope']['jurisdiction']='CA'
    inspect_case('US_source_for_Canadian_jurisdiction',wrong_scope,deepcopy(observed))
    partial=deepcopy(observed);partial['retrieved_chunk_ids']=partial['retrieved_chunk_ids'][:1];partial['citations']=partial['retrieved_chunk_ids']
    inspect_case('partial_retrieval_loses_required_quote',base,partial)
    text_task=deepcopy(base);text_task['answer_contract']={'version':1,'type':'text'};text_task['scoring']='contains'
    convincing=deepcopy(observed);convincing['answer']='70 cents per mile, and every worker is guaranteed an unlimited deduction.';convincing['raw_answer']=convincing['answer'];convincing['actual']=convincing['answer'];convincing['answer_contract_valid']=True
    inspect_case('convincing_additional_claim_needs_semantic_review',text_task,convincing)
    # Deterministic actual retrieval/screening of a real historical source, no synthetic source text.
    with tempfile.TemporaryDirectory(prefix='irs-stale-control-') as temp:
        root=Path(temp)/'variant';shutil.copytree(Path(after['_root']),root,ignore=shutil.ignore_patterns('.sourceroi'))
        folder=root/'sources/archive';folder.mkdir();shutil.copy2(BASE/'raw/notice-2024.pdf',folder/'2024 notice.pdf')
        cfg=json.loads((root/'project.json').read_text());cfg['sources'].append({'id':'archive','name':'Historical IRS 2024','path':'sources/archive','authority':'IRS','jurisdiction':'US','policy_scope':'IRS standard mileage schedule','effective_from':'2024-01-01','effective_to':'2025-01-01'})
        (root/'project.json').write_text(json.dumps(cfg));variant=read_config(root)
        vd,vc=scan_sources(variant);selected,_=select_context(base['question'],vc,variant)
        _,screen=precheck(base['question'],selected,variant,base.get('evidence_contract'),base.get('scope'))
        dated=deepcopy(base);dated['scope']['as_of']='2025-06-01';eligible,dated_screen=precheck(base['question'],selected,variant,base.get('evidence_contract'),dated['scope'])
        controls.append({'case':'authoritative_2024_and_2025_sources_coexist','origin':'real archived PDF added in isolated temporary configuration; actual retrieval/screen only','documents':{d['id']:d['fingerprint'] for d in vd},'selected_ids':[c['id'] for c in selected],'screen':screen,'dated_screen':dated_screen,'actual_new_model_calls':0,'interpretation':'Selected archive may or may not reach this query; no model outcome fabricated'})
    # Overly strict alias demonstrates a legitimate supported answer can be rejected.
    _,alias_screen=precheck(base['question'],[c for c in chunks if c['id'] in observed['retrieved_chunk_ids']],after,{'version':1,'subject_aliases':[['automotive reimbursement quantum']]},base.get('scope'))
    controls.append({'case':'legitimate_update_rejected_by_bad_alias_contract','origin':'explicitly misconfigured necessary condition, not an agent regeneration','screen':alias_screen,'actual_new_model_calls':0})
    return controls


def main():
    if (ART/'analysis.json').exists():raise ValueError('Analysis exists')
    release=json.loads((ART/'release.json').read_text());annotations={x['id']:x for x in json.loads((ART/'frozen-annotations.json').read_text())['annotations']}
    before=read_config(BASE/'accepted');after=read_config(BASE/'candidate');tasks={t['id']:t for t in load_benchmark(after)}
    stages={};details=[]
    for stage,cfg,version in [('baseline',before,'before'),('candidate',after,'after')]:
        _,chunks=scan_sources(cfg);rows=release.get(stage,{}).get('tasks',[]);scores=[]
        for row in rows:
            t=revised(tasks[row['id']],annotations[row['id']],version)
            fmt,_=check(row['answer'] if row['answer']=='INSUFFICIENT_EVIDENCE' else row.get('raw_answer',row['answer']),t.get('answer_contract'))
            correct=grade(row['answer'],t) and fmt and row.get('response_complete',True)
            retrieved=evidence_coverage(t,row,chunks);cited=evidence_coverage(t,{'retrieved_chunk_ids':row['citations']},chunks)
            scores.append({'id':t['id'],'correct':correct,'supported':t['expected']!='INSUFFICIENT_EVIDENCE','answer':row['answer'],
                'abstained':row['answer']=='INSUFFICIENT_EVIDENCE','origin':row.get('answer_origin'),'format_valid':fmt,
                'retrieved_coverage':retrieved,'cited_coverage':cited,'citations':row['citations'],'invalid_citations':row['invalid_citations'],
                'diagnosis':diagnose(t,row,chunks,cfg) if not correct or retrieved not in (1,None) else None})
        supported=[r for r in scores if r['supported']];unsupported=[r for r in scores if not r['supported']]
        stages[stage]={'registered_correct':sum(r['correct'] for r in scores),'tasks':len(scores),'supported_correct':sum(r['correct'] for r in supported),'supported_tasks':len(supported),
            'false_abstentions':sum(r['abstained'] for r in supported),'unsupported_questions':len(unsupported),'unsupported_factual_answers':sum(not r['abstained'] for r in unsupported),
            'unsupported_model_generation_count':sum(r['origin']=='model' for r in unsupported),'responses_with_citations':sum(bool(r['citations']) for r in scores),
            'invalid_citation_ids':sum(len(r['invalid_citations']) for r in scores),'full_retrieved_reference_coverage_tasks':sum(r['retrieved_coverage']==1 for r in supported),
            'full_cited_reference_coverage_tasks':sum(r['cited_coverage']==1 for r in supported),'independent_semantic_correctness':None,'per_task':scores}
    c=conventional(before,after,release,annotations)
    replay_start=time.perf_counter()
    spec=json.loads((ART/'change-plan-v2.json').read_text());approval=json.loads((ART/'technical-development-review-v2.json').read_text())
    def recorded_callback(cfg,questions):return deepcopy(release['baseline'] if cfg['_root']==before['_root'] else release['candidate'])
    replay=a.execute(before,after,spec,approval=approval,callback=recorded_callback,policy='strict_grounded',max_calls=12,max_seconds=60,persist=False)
    replay_ms=(time.perf_counter()-replay_start)*1000
    faults=stress_controls(after,release,tasks)
    events=json.loads((ART/'execution-log.json').read_text())
    request_files=sorted((ART/'calls').glob('*-request.json'));response_files=sorted((ART/'calls').glob('*-response.json'))
    assert len(request_files)==len(events['events'])==events['actual_generation_requests']<=12
    assert all(e.get('finished_seconds') is not None for e in events['events'])
    model_seconds=sum(e['finished_seconds']-e['started_seconds'] for e in events['events'])
    total_tokens=sum((e.get('usage') or {}).get('prompt_tokens',0)+(e.get('usage') or {}).get('completion_tokens',0) for e in events['events'])
    main_candidate={r['id']:r for r in stages['candidate']['per_task']};main_before={r['id']:r for r in stages['baseline']['per_task']}
    lost=[k for k in main_before if main_before[k]['correct'] and not main_candidate[k]['correct']]
    extras=json.loads((ART/'actual-ablation-and-topk.json').read_text())
    source_supported={t['id'] for t in tasks.values() if t['scope']['jurisdiction']=='US'};predicted={r['task_id'] for r in spec['impact'] if r['potentially_affected']}
    result={'kind':'real_irs_e2e_analysis','labels':'Source-derived Codex development labels, frozen before inference; not independently human reviewed',
        'stages':stages,'actual_release_verdict':release['verdict'],'release_checks':release['check_statuses'],'new_lost_tasks':lost,
        'protected_task_results':{k:{'before':main_before[k]['correct'],'after':main_candidate[k]['correct']} for k in approval['protected_tasks']},
        'maintained_combined_baseline':c,'source_roi_replay_verdict':replay['verdict'],'source_roi_replay_overhead_ms':replay_ms,
        'comparison_tie':c['verdict']==release['verdict']==replay['verdict'],
        'overhead_note':'Both replay checkers reuse the exact same model outputs and verify the frozen corpus. Timings include different bookkeeping/diagnosis work, no inference; single exploratory local timing, not a labor/cost advantage.',
        'actual_generation_requests':events['actual_generation_requests'],'successful_response_files':len(response_files),'reported_tokens':total_tokens,
        'generation_request_seconds':model_seconds,'whole_run_seconds':events['elapsed_seconds'],'external_spend_usd':0,
        'impact':{'predicted':sorted(predicted),'source_dependent_applicable_development_oracle':sorted(source_supported),
            'recall':len(predicted&source_supported)/len(source_supported),'precision':len(predicted&source_supported)/len(predicted),
            'false_positive':sorted(predicted-source_supported),'expected_answer_changes':[k for k,x in annotations.items() if x['expected_behavior_change']],
            'limitation':'One changed document; broad dependency mapping is not fact-selective human-validated recall. Protected tasks can still be source-dependent.'},
        'ablation_and_topk':extras,'stress_controls':faults,'independent_human_reviews':0,'human_maintenance_time_saved':None,
        'production_modified':False}
    dump(ART/'analysis.json',result);dump(ART/'replay-release.json',replay)
    print(json.dumps({'stages':{k:{key:v for key,v in x.items() if key!='per_task'} for k,x in stages.items()},'release':release['verdict'],'baseline':c['verdict'],'lost':lost,'requests':events['actual_generation_requests'],'tokens':total_tokens,'seconds':events['elapsed_seconds']},indent=2))

if __name__=='__main__':main()
