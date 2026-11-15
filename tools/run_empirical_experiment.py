"""Real source-aware RAG experiment; full benchmark needs separate authorization.

Dry-run captures real prompt construction without generating answers. Smoke is
strictly an accounting smoke, not an independently validated benchmark result.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.engine import evaluate_variant
from sourceroi.live.experiment import Experiment,reconcile
from sourceroi.live.native_gate import CERTIFICATE
from sourceroi.live import assurance as assurance
from sourceroi.live.data_ci import digest,evidence_coverage,run_data_ci
from sourceroi.live.grade import grade
from sourceroi.live.diagnosis import diagnose


def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as file:json.dump(value,file,indent=2,ensure_ascii=False);file.write('\n')


def check_freeze(root):
    root=Path(root)
    for rel,value in json.loads((root/'freeze-manifest.json').read_text()).items():
        path=root/rel
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=value:raise ValueError('Frozen experiment input changed: '+rel)


def evaluate_one(cfg,task):
    # Production retrieval rule from the question, not expected labels: CURRENT
    # means registered current source. Cross-version tasks search all editions.
    docs,chunks=scan_sources(cfg)
    if not cfg.get('settings',{}).get('retrieval_contract'):raise ValueError('Declare the application retrieval_contract before freezing a new benchmark; historical frozen runs are replay-only')
    result=evaluate_variant(cfg,[task],chunks,[])
    row=result['tasks'][0]
    manifest={d['id']:d['fingerprint'] for d in docs}
    row.update(knowledge_manifest=manifest,knowledge_version=digest(manifest))
    context=[c for c in chunks if c['id'] in row['retrieved_chunk_ids']]
    return row,context


def metrics(rows,tasks):
    keyed={t['id']:t for t in tasks};supported=[];unsupported=[]
    for row in rows:
        task=keyed[row['id']]
        (unsupported if task['expected']=='INSUFFICIENT_EVIDENCE' else supported).append((row,task))
    def rate(n,d):return n/d if d else None
    correct=sum(grade(r['actual'],t) and r.get('answer_contract_valid',True) for r,t in supported)
    abstained=sum(r['actual']=='INSUFFICIENT_EVIDENCE' for r,t in supported)
    rejected=sum(r['actual']=='INSUFFICIENT_EVIDENCE' for r,t in unsupported)
    factual=[r for r in rows if r['actual']!='INSUFFICIENT_EVIDENCE']
    citation_fail=sum(bool(r.get('invalid_citations')) or not r.get('citations') for r in factual)
    return {'supported_correct':correct,'supported_n':len(supported),'supported_accuracy':rate(correct,len(supported)),
        'supported_false_abstentions':abstained,'supported_false_abstention_rate':rate(abstained,len(supported)),
        'unsupported_rejections':rejected,'unsupported_n':len(unsupported),'unsupported_rejection_rate':rate(rejected,len(unsupported)),
        'factual_answers':len(factual),'citation_id_failures':citation_fail,'citation_id_failure_rate':rate(citation_fail,len(factual)),
        'model_generated_rows':sum(r.get('usage_source')=='provider_reported' for r in rows),
        'semantic_citation_correctness':None,'independent_review':'PENDING'}


def conventional(cfg,tasks,rows,contexts):
    """Maintained ordinary checks; shared labels, outputs, provenance and quotes.

    Independent logic for answer/citation/version/scope/reference checks. No call
    into SourceROI release-policy decision code and no weakened stale labels.
    """
    docs,chunks=scan_sources(cfg);manifest={d['id']:d['fingerprint'] for d in docs}
    source={s['id']:s for s in cfg['sources']};details=[]
    for task in tasks:
        row=next((r for r in rows if r['id']==task['id']),None)
        if row is None:details.append({'id':task['id'],'status':'INCONCLUSIVE'});continue
        known={c['id']:c for c in contexts[task['id']]};cites=row.get('citations',[])
        factual=row['actual']!='INSUFFICIENT_EVIDENCE'
        correct=grade(row['actual'],task) and row.get('answer_contract_valid',True)
        ids_valid=not row.get('invalid_citations') and all(c in known for c in cites) and (bool(cites) or not factual)
        provenance=row.get('knowledge_manifest')==manifest and row.get('knowledge_version')==digest(manifest)
        coverage=evidence_coverage(task,{'retrieved_chunk_ids':cites},list(known.values()))
        scope_ok=True
        for cid in cites:
            if cid not in known:continue
            meta=source[known[cid]['source_id']];scope=task.get('scope',{})
            if scope.get('jurisdiction') and meta.get('jurisdiction') not in (scope['jurisdiction'],'global'):scope_ok=False
            if scope.get('policy_scope') and meta.get('policy_scope')!=scope['policy_scope']:scope_ok=False
            when=scope.get('as_of')
            if when and (meta.get('effective_from') and when<meta['effective_from'] or meta.get('effective_to') and when>=meta['effective_to']):scope_ok=False
        state='BLOCK' if not correct or not ids_valid or not scope_ok or factual and coverage is not None and coverage<1 else 'INCONCLUSIVE' if not provenance or not row.get('response_complete',True) else 'REVIEW'
        details.append({'id':task['id'],'status':state,'answer_correct':correct,'citation_ids_valid':bool(ids_valid),
            'source_version_valid':provenance,'scope_valid':scope_ok,'quoted_evidence_coverage':coverage,'semantic_review':'PENDING'})
    verdict=next((v for v in ('BLOCK','INCONCLUSIVE','REVIEW') if any(r['status']==v for r in details)),'INCONCLUSIVE')
    return {'verdict':verdict,'tasks':details,'authority':'Identical frozen development labels, replacement evidence, scope and absent independent semantic reviews',
        'independent_semantic_quality':None,'human_effort_seconds':None}


def dry_run(root,output):
    check_freeze(root);root=Path(root);output=Path(output)
    if output.exists():raise ValueError('Choose a fresh output directory')
    output.mkdir(parents=True)
    captured=[];traces=[]
    class Captured(RuntimeError):pass
    def capture(url,body,*args):
        captured.append({'url':url,'request':body,'generation_executed':False});raise Captured()
    for version in ('accepted','candidate'):
        cfg=read_config(root/version);cfg['_experiment_transport']=capture
        for task in load_benchmark(cfg):
            try:
                row,context=evaluate_one(cfg,task)
                traces.append({'version':version,'id':task['id'],'status':'SOFTWARE_ABSTENTION_NO_MODEL','row':row,'context':context})
            except Captured:
                traces.append({'version':version,'id':task['id'],'status':'PROMPT_CAPTURED_NOT_DISPATCHED'})
    dump(output/'prompt-construction.json',captured);dump(output/'retrieval-prechecks.json',traces)
    dump(output/'summary.json',{'status':'VERIFIED_OFFLINE_HARNESS_ONLY','paired_tasks':len(traces),'captured_generation_requests':len(captured),
        'real_model_calls':0,'model_answers':None,'real_accuracy':None,'full_benchmark_authorization':'PENDING'})
    return {'paired_tasks':len(traces),'captured_requests':len(captured),'model_calls':0}


def execute(root,output,authorization,*,smoke=False,review_path=None,conventional_packet=None):
    check_freeze(root);root=Path(root);output=Path(output)
    auth=json.loads(Path(authorization).read_text())
    if auth.get('scope')!=('accounting_smoke' if smoke else 'benchmark'):raise ValueError('Authorization scope mismatch')
    if not smoke and auth.get('status')!='approved':raise ValueError('Full benchmark has no approved generation/runtime/retry/spend budget')
    from sourceroi.live.evaluation_inputs import maintained_tasks as apply_review,packet,assert_parity
    plan=json.loads((root/'change-plan.json').read_text())
    if not smoke and review_path is None:raise ValueError('Supply an explicit pre-execution review record; the harness cannot approve a DRAFT after observing outputs')
    review=json.loads(Path(review_path).read_text()) if review_path else None
    assurance.validate_release_inputs(read_config(root/'accepted'),read_config(root/'candidate'),plan,review)
    comparison_inputs={}
    for version in ('accepted','candidate'):
        cfg=read_config(root/version)
        if not cfg.get('settings',{}).get('retrieval_contract'):raise ValueError('Explicit frozen retrieval_contract required for app/Data CI parity')
        tasks=load_benchmark(cfg)
        if version=='candidate':tasks=apply_review(tasks,plan,review)
        comparison_inputs[version]=packet(cfg,tasks,spec=plan,approval=review)
    external=json.loads(Path(conventional_packet).read_text()) if conventional_packet else deepcopy(comparison_inputs)
    for version in comparison_inputs:assert_parity(comparison_inputs[version],external[version])
    if output.exists():raise ValueError('Output exists; no implicit retries or overwrites')
    output.mkdir(parents=True)
    dump(output/'authorization.json',auth)
    dump(output/'comparison-inputs-sourceroi.json',comparison_inputs)
    dump(output/'comparison-inputs-conventional.json',external)
    all_rows={};all_contexts={};cfgs={};tasksets={};runtime=output/'runtime'
    max_calls=2 if smoke else auth['max_attempts'];max_seconds=30 if smoke else auth['max_seconds']
    failure=None
    try:
        with Experiment(runtime,max_calls=max_calls,max_seconds=max_seconds,native_certificate=CERTIFICATE,authorization=authorization) as runner:
            for version in ('accepted','candidate'):
                cfg=read_config(root/version);cfgs[version]=cfg
                tasks=load_benchmark(cfg);selected=tasks[:1] if smoke else tasks
                all_rows[version]=[];all_contexts[version]={};tasksets[version]=selected
                for task in selected:
                    row,context=evaluate_one(runner.configure(cfg),task)
                    all_rows[version].append(row);all_contexts[version][task['id']]=context
                    dump(output/(version+'-'+task['id']+'.json'),{'task':task,'row':row,'retrieved_evidence':context})
            # Full Data CI intentionally obtains a second recorded paired run;
            # there is no hidden replay masquerading as fresh model execution.
            if not smoke:
                ci=run_data_ci(runner.configure(cfgs['accepted']),runner.configure(cfgs['candidate']),max_tasks=10)
                ci['experiment_note']='Separate actual built-in retrieval/Data CI run using original frozen labels; not the maintained-label comparator and not the primary CURRENT-source retrieval wrapper.'
                dump(output/'data-ci.json',ci)
    except BaseException as exc:
        failure={'type':type(exc).__name__,'message':str(exc)}
    audit=reconcile(runtime) if (runtime/'manifest.json').exists() else {'status':'INCONCLUSIVE','failures':['no_runtime_manifest']}
    # Read-only comparisons consume the exact captured real responses, never
    # create alternative "model" answers or call the application again.
    comparisons={};metrics_by_version={};maintained_tasks={}
    annotations=json.loads((root/'frozen-labels.json').read_text())['annotations']
    for version,rows in all_rows.items():
        tasks=deepcopy(tasksets[version])
        if version=='candidate':tasks=apply_review(tasks,plan,review)
        maintained_tasks[version]=tasks
        metrics_by_version[version]=metrics(rows,tasks)
        comparisons[version]=conventional(cfgs[version],tasks,rows,all_contexts[version])
    if not smoke and not failure and all(len(rows)==10 for rows in all_rows.values()):
        from sourceroi.live.release_policy import resolve
        dump(output/'supplied-review.json',review)
        def cached_actual_trace(cfg,tasks):
            version='accepted' if Path(cfg['_root'])==Path(cfgs['accepted']['_root']) else 'candidate'
            table={r['id']:r for r in all_rows[version]}
            return {'tasks':[deepcopy(table[t['id']]) for t in tasks],'metrics':{},'adapter_identity':'Replay of captured actual native generation traces; no additional inference'}
        t0=time.perf_counter()
        release=assurance.execute(cfgs['accepted'],cfgs['candidate'],plan,approval=review,callback=cached_actual_trace,max_calls=20,max_seconds=90,policy='strict_grounded')
        sr_ms=(time.perf_counter()-t0)*1000;dump(output/'strict-release.json',release)
        failures=[]
        _,chunks=scan_sources(cfgs['candidate'])
        for t in maintained_tasks['candidate']:
            r=deepcopy(next(r for r in all_rows['candidate'] if r['id']==t['id']))
            r['correct']=grade(r['actual'],t) and r.get('answer_contract_valid',True)
            if not r['correct']:failures.append(diagnose(t,r,chunks,cfgs['candidate']))
        dump(output/'diagnosis.json',failures)
        comparisons['paired']={'sourceroi_verdict':release['verdict'],'conventional_verdict':comparisons['candidate']['verdict'],
            'identical_outputs':True,'source_roi_scoring_overhead_ms':sr_ms,'human_effort_savings':None,
            'differentiated_detection_claim':False,'note':'Same generated answers, maintained labels/references and absent independent review; do not infer superiority from workflow fields'}
    result={'status':'INCONCLUSIVE' if failure or audit['status']!='RECONCILED' else 'RECONCILED_ACCOUNTING_SMOKE' if smoke else 'COMPLETED_DEVELOPMENT_EXPERIMENT',
        'failure':failure,'runtime_accounting':audit,'scope':auth['scope'],'metrics':metrics_by_version,'comparison':comparisons,
        'independent_semantic_review':None,'customer_value':None,'external_spend_usd':0}
    dump(output/'results.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['dry-run','smoke','run'])
    p.add_argument('--benchmark',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--authorization',type=Path);p.add_argument('--review',type=Path);p.add_argument('--conventional-packet',type=Path)
    a=p.parse_args()
    try:
        result=dry_run(a.benchmark,a.output) if a.mode=='dry-run' else execute(a.benchmark,a.output,a.authorization,smoke=a.mode=='smoke',review_path=a.review,conventional_packet=a.conventional_packet)
        print(json.dumps(result,indent=2));raise SystemExit(5 if result.get('status')=='INCONCLUSIVE' else 0)
    except (ValueError,OSError,TypeError,KeyError) as exc:p.exit(2,'Experiment not dispatched: '+str(exc)+'\n')
