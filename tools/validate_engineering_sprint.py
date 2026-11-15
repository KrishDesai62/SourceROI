"""Bounded local development experiment; no independent-label or deployment claim.

Prepare freezes new questions and policy configurations before inference. Existing
IRS artifacts are read-only. Actual POST attempts, including errors, count against
the global cap. Incomplete runs retain the ledger and cannot qualify.
"""
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import time
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'workspace/.deps'))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import load_benchmark, scan_sources
from sourceroi.live.data_ci import digest, evidence_coverage
from sourceroi.live.engine import evaluate_variant
from sourceroi.live.validation import Budget, optimize
from sourceroi.live.policies import select_context
from sourceroi.live.release_policy import sample_for, inspect
from sourceroi.live.reliability_review import packet
from sourceroi.live import db

ART=ROOT/'docs/artifacts/engineering-sprint'
BASE=ROOT/'workspace/engineering-sprint'
NAMES=('original','top_k_1','passage_coverage')


def dump(path,value):
    path=Path(path)
    with path.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    if BASE.exists() or (ART/'plan.json').exists():raise ValueError('Immutable destination already exists')
    source=ROOT/'workspace/irs-e2e/candidate'
    cfg=json.loads((source/'project.json').read_text())
    # New tasks target other predicates/periods in the original authoritative PDF.
    # They are Codex development labels, not independently reviewed or held-out.
    doc='current::CURRENT notice.pdf'
    cases=[('favr_ceiling','In the 2025 notice, what is the maximum standard automobile cost in dollars for a FAVR plan?',
            '61200',['$61,200 for automobiles'],[['FAVR']]),
           ('depreciation_2025','For 2025, what portion of the business standard mileage rate is treated as depreciation, in cents per mile?',
            '33',['33 cents per mile for 2025'],[['depreciation']]),
           ('depreciation_difference','What is the 2025 depreciation portion minus the 2023 depreciation portion, in cents per mile?',
            '5',['33 cents per mile for 2025','28 cents per mile for 2023'],[['depreciation']]),
           ('canadian_favr','What maximum automobile cost does this collection authorize for a Canadian FAVR plan?',
            'INSUFFICIENT_EVIDENCE',[],[['FAVR']])]
    tasks=[]
    from sourceroi.live.ingest import _extract
    text=_extract(source/'sources/current/CURRENT notice.pdf')
    for ident,q,answer,quotes,aliases in cases:
        assert all(quote in text for quote in quotes)
        tasks.append({'id':ident,'question':q,'expected':answer,'scoring':'exact' if answer=='INSUFFICIENT_EVIDENCE' else 'numeric',
            'category':'fresh-development','split':'development','group_id':'IRS-2025-existing-document-family',
            'requires_grounding':True,'review_status':'Codex development annotation, not independently reviewed',
            'evidence':[{'document_id':doc,'quote':quote} for quote in quotes],
            'answer_contract':{'version':1,'type':'numeric'},'evidence_contract':{'version':1,'subject_aliases':aliases},
            'scope':{'jurisdiction':'CA' if ident=='canadian_favr' else 'US','policy_scope':'IRS standard mileage schedule'}})
    BASE.mkdir()
    for name in NAMES+('optimizer',):
        root=BASE/name;root.mkdir();shutil.copytree(source/'sources',root/'sources')
        local=deepcopy(cfg);local['id']='engineering-'+name.replace('_','-');local['measurement_kind']='local_generation'
        local['settings'].update(max_model_calls_per_run=12,max_run_seconds=120,chunk_strategy='fixed',retrieval_policy={'name':'original'})
        if name=='top_k_1':local['settings']['retrieval_policy']={'name':'top_k','k':1}
        if name=='passage_coverage':local['settings'].update(chunk_strategy='sentences',retrieval_policy={'name':'passage_coverage','k':3})
        if name=='optimizer':local['settings'].update(max_model_calls_per_run=4)
        (root/'project.json').write_text(json.dumps(local,indent=2)+'\n')
        # Optimizer uses one explicitly declared development task; no final set.
        (root/'benchmark.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in (tasks[:1] if name=='optimizer' else tasks)))
    dump(ART/'frozen-tasks.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),'labels':'Codex source-derived development annotations; independent final PENDING','tasks':tasks})
    dump(ART/'plan.json',{'max_actual_generation_requests':12,'max_seconds':120,'configurations':list(NAMES),
        'tasks_sha256':digest(tasks),'source_pdf_sha256':sha(source/'sources/current/CURRENT notice.pdf'),
        'quality_constraints':{'accuracy_floor':1.0,'supported_accuracy_floor':1.0,'max_regressions':0,'reference_coverage_floor':1.0,'invalid_citations':0,'false_abstentions':0},
        'independent_semantic_metrics':None,'independent_final_status':'PENDING',
        'optimizer_allocation':'Existing optimizer on one fresh development task: four logical evaluations, at most two generation requests because both source exclusions have empty context. Shared POST guard enforces global 12/120 regardless.',
        'baseline_quality_requirement':'Poor baseline does not establish quality preservation. No semantic or deployment claim without independent reviewers.',
        'external_spend_usd':0,'hardware_cost_usd':None})
    code=list((ROOT/'sourceroi/live').glob('*.py'))+[Path(__file__).resolve()]
    with tarfile.open(ART/'as-run-code.tar.gz','w:gz') as archive:
        for f in code:archive.add(f,arcname=str(f.relative_to(ROOT)))
    dump(ART/'freeze.json',{'created_at':datetime.now(timezone.utc).isoformat(),'python':sys.version,
        'files':{str(f.relative_to(ROOT)):sha(f) for f in code},
        'configuration_files':{str(f.relative_to(ROOT)):sha(f) for f in BASE.rglob('*') if f.is_file()},
        'model_manifest':json.loads((ROOT/'workspace/.local-llm/manifest.json').read_text())})
    print('Prepared four fresh development tasks and three fixed policies; no model calls.')


def run():
    import sourceroi.live.provider as provider
    if (ART/'results.json').exists() or (ART/'execution-log.json').exists():raise ValueError('Experiment already attempted; evidence is immutable')
    frozen=json.loads((ART/'freeze.json').read_text())
    assert all(sha(ROOT/path)==value for path,value in frozen['configuration_files'].items())
    assert all(sha(ROOT/path)==value for path,value in frozen['files'].items())
    (ART/'calls').mkdir();events=[];start=time.monotonic();post=provider._post
    report={'kind':'engineering_development','status':'incomplete','variants':{},'external_spend_usd':0,'independent_final_status':'PENDING'}
    def observed(url,body,timeout,*args,**kwargs):
        if urlparse(url).hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('Local only')
        left=120-(time.monotonic()-start)
        if left<=0:raise ValueError('Global time cap reached')
        if url.endswith('/chat/completions'):
            if len(events)>=12:raise ValueError('Global actual call cap reached')
            event={'sequence':len(events)+1,'started_seconds':time.monotonic()-start,'request_sha256':digest(body)};events.append(event)
            dump(ART/f'calls/{len(events):02d}-request.json',body)
            try:
                response=post(url,body,min(timeout,left),*args,**kwargs)
                dump(ART/f'calls/{event["sequence"]:02d}-response.json',response);event['usage']=response.get('usage');return response
            except Exception as exc:event['error_type']=type(exc).__name__;raise
            finally:event['finished_seconds']=time.monotonic()-start
        return post(url,body,min(timeout,left),*args,**kwargs)
    provider._post=observed
    try:
        for name in NAMES:
            cfg=read_config(BASE/name);tasks=load_benchmark(cfg);docs,chunks=scan_sources(cfg)
            cfg['_experiment_budget']=Budget({'max_model_calls_per_run':12-len(events),'max_run_seconds':max(.001,120-(time.monotonic()-start))})
            rid=db.begin(cfg,'engineering_development',[]);cfg['_partial_tasks']=[]
            try:
                variant=evaluate_variant(cfg,tasks,chunks,[])
                reviews=[];checks=[]
                for task,row in zip(tasks,variant['tasks']):
                    row['literal_reference_coverage']=evidence_coverage(task,row,chunks)
                    reviews.append(packet(sample_for(task,row,chunks,cfg,digest({d['id']:d['fingerprint'] for d in docs}))))
                    checks.append(inspect(task,row,chunks,cfg,reviews[-1]['sample']['source_version'],builtin=True))
                entry={'run_id':rid,'variant':variant,'checks':checks,'review_items':reviews}
                report['variants'][name]=entry;dump(ART/f'{name}.json',entry);db.finish(cfg,rid,entry)
            except Exception as exc:
                db.finish(cfg,rid,{'partial_tasks':cfg['_partial_tasks']},type(exc).__name__);raise
        cfg=read_config(BASE/'optimizer');remaining=max(.001,120-(time.monotonic()-start));cfg['settings']['max_run_seconds']=remaining
        rid=db.begin(cfg,'optimization_validation',[])
        try:
            opt=optimize(cfg,quality_floor=1,min_citation_rate=1,objective='token_budget',max_tasks=1,max_candidates=1,max_accuracy_drop=0,max_regressions=0)
            report['optimizer']={'run_id':rid,'report':opt};db.finish(cfg,rid,opt)
        except Exception as exc:
            report['optimizer']={'status':'incomplete','error':str(exc)};db.finish(cfg,rid,None,type(exc).__name__)
        report['status']='completed'
    except Exception as exc:report['error']={'type':type(exc).__name__,'message':str(exc)}
    finally:
        provider._post=post
        dump(ART/'execution-log.json',{'actual_generation_requests':len(events),'events':events,'elapsed_seconds':time.monotonic()-start,
            'max_calls':12,'max_seconds':120,'external_spend_usd':0,'count_method':'Actual POST attempts including errors; tokenization excluded'})
        dump(ART/'results.json',report)
    print(json.dumps({'status':report['status'],'actual_calls':len(events),'seconds':time.monotonic()-start,'error':report.get('error')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);args=p.parse_args()
    prepare() if args.action=='prepare' else run()
