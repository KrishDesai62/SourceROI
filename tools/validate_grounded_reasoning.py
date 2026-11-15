"""Frozen development comparison: three real model paths and an opt-in calculator.

IRS cases are exposed; finance is a clearly authored synthetic fixture. No
independent final labels/reviews are supplied. At most 12 actual local generation
attempts / 120 seconds globally, including failures. Never overwrite evidence.
"""
from copy import deepcopy
from datetime import datetime,timezone
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
from sourceroi.live import db,facts
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark,_extract
from sourceroi.live.engine import evaluate_variant
from sourceroi.live.data_ci import digest,evidence_coverage
from sourceroi.live.validation import Budget
from sourceroi.live.release_policy import inspect,sample_for
from sourceroi.live.reliability_review import packet

ART=ROOT/'docs/artifacts/grounded-reasoning';BASE=ROOT/'workspace/grounded-reasoning'
NAMES=('fixed','passage','predicate','source_calculation')
REVIEWER='Codex technical development contract author; not independent human review'


def dump(path,value):
    path=Path(path)
    with path.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    if BASE.exists() or (ART/'plan.json').exists():raise ValueError('Immutable destination exists')
    original=ROOT/'workspace/irs-e2e/candidate'
    old=json.loads((original/'project.json').read_text());text=_extract(original/'sources/current/CURRENT notice.pdf')
    finance='Synthetic engineering fixture, not a real company report.\nExampleCo revenue is 900 dollars for Q1, and 1040 dollars for Q2.\n'
    def spec(op,periods,financial=False):
        return {'version':1,'operation':op,'operands':[{'subject':'ExampleCo' if financial else 'business standard mileage rate',
            'predicate':'revenue' if financial else 'treated as depreciation','unit':'dollars' if financial else 'cents per mile','period':p} for p in periods]}
    tasks=[]
    rows=[('depreciation_lookup','For 2025, what portion of the business standard mileage rate is treated as depreciation, in cents per mile?',
            '33',spec('lookup',['2025']),['33 cents per mile for 2025'],False),
          ('depreciation_difference','What is the 2025 depreciation portion minus the 2023 depreciation portion, in cents per mile?',
            '5',spec('subtract',['2025','2023']),['33 cents per mile for 2025','28 cents per mile for 2023'],False),
          ('financial_difference','What is ExampleCo revenue for Q2 minus Q1, in dollars?',
            '140',spec('subtract',['Q2','Q1'],True),['900 dollars for Q1','1040 dollars for Q2'],True),
          ('missing_period','For 2027, what portion of the business standard mileage rate is treated as depreciation, in cents per mile?',
            'INSUFFICIENT_EVIDENCE',spec('lookup',['2027']),[],False)]
    for ident,q,expected,calculation,quotes,financial in rows:
        corpus=finance if financial else text;assert all(quote in corpus for quote in quotes)
        scope={'jurisdiction':'US','policy_scope':'synthetic financial fixture' if financial else 'IRS standard mileage schedule'}
        task={'id':ident,'question':q,'expected':expected,'scoring':'exact' if expected=='INSUFFICIENT_EVIDENCE' else 'numeric',
            'category':'synthetic-development' if financial else 'exposed-IRS-development','split':'development',
            'group_id':'synthetic-finance' if financial else 'exposed-IRS','review_status':'Codex development labels; no independent review',
            'requires_grounding':True,'scope':scope,'answer_contract':{'version':1,'type':'numeric'},
            'evidence_contract':{'version':1,'subject_aliases':[['ExampleCo' if financial else 'depreciation']]},
            'evidence':[{'document_id':'finance::synthetic.txt' if financial else 'current::CURRENT notice.pdf','quote':quote} for quote in quotes],
            'calculation_contract':calculation,'calculation_authorization':facts.authorize(q,scope,calculation,reviewer=REVIEWER,
                rationale='Explicit development '+calculation['operation']+' on named question periods; operation chosen from question before outputs, never from expected value; no independent semantic approval')}
        tasks.append(task)
    BASE.mkdir()
    for name in NAMES:
        root=BASE/name;root.mkdir();shutil.copytree(original/'sources',root/'sources');(root/'sources/finance').mkdir()
        (root/'sources/finance/synthetic.txt').write_text(finance)
        cfg=deepcopy(old);cfg['id']='grounded-'+name.replace('_','-');cfg['measurement_kind']='local_generation'
        cfg['sources'].append({'id':'finance','name':'Clearly synthetic development financial fixture','path':'sources/finance','authority':'Codex-authored synthetic development fixture','jurisdiction':'US','policy_scope':'synthetic financial fixture'})
        cfg['settings'].update(max_chunks=3,chunk_strategy='fixed' if name=='fixed' else 'sentences',
            retrieval_policy={'name':'original' if name=='fixed' else 'passage_coverage' if name=='passage' else 'predicate'},
            answering_mode='source_calculation' if name=='source_calculation' else 'model',calculation_reviewers=[REVIEWER],
            max_tasks_per_run=4,max_model_calls_per_run=12,max_run_seconds=120)
        (root/'project.json').write_text(json.dumps(cfg,indent=2)+'\n')
        (root/'benchmark.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in tasks))
        load_benchmark(read_config(root))
    dump(ART/'frozen-tasks.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),'tasks':tasks,
        'status':'Development only; independent hidden final PENDING','operation_authority':REVIEWER,
        'sources':'Official IRS historical notice + explicitly synthetic financial fixture; no customer data'})
    dump(ART/'plan.json',{'max_actual_generation_attempts':12,'max_total_seconds':120,'policies':list(NAMES),
        'quality_rule':{'supported_accuracy':1.0,'unsupported_factual_answers':0,'false_abstentions':0,'full_required_reference_recall':1.0,'invalid_citation_ids':0,'incomplete_tasks':0},
        'independent_grounding':None,'independent_final':'PENDING','optimization':'Do not start further optimization unless a reliable reference is established; deterministic mode is separate from LLM context savings',
        'irs_pdf_sha256':sha(original/'sources/current/CURRENT notice.pdf'),'model':old['model'],'task_hash':digest(tasks),
        'independence':'Codex development authorizations/labels only; reviewer allowlist is operator configuration, not authenticated independence','external_spend_usd':0})
    code=list((ROOT/'sourceroi/live').glob('*.py'))+[Path(__file__).resolve()]
    with tarfile.open(ART/'as-run-code.tar.gz','w:gz') as tar:
        for p in code:tar.add(p,arcname=str(p.relative_to(ROOT)))
    dump(ART/'freeze.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),'python':sys.version,
        'code_hashes':{str(p.relative_to(ROOT)):sha(p) for p in code},
        'input_hashes':{str(p.relative_to(ROOT)):sha(p) for p in BASE.rglob('*') if p.is_file()},
        'model_runtime':json.loads((ROOT/'workspace/.local-llm/manifest.json').read_text())})
    print('Frozen four development tasks and explicit task authorizations; zero inference.')


def run():
    import sourceroi.live.provider as provider
    if (ART/'calls').exists() or (ART/'results.json').exists():raise ValueError('An attempt already exists; immutable evidence')
    freeze=json.loads((ART/'freeze.json').read_text())
    assert all(sha(ROOT/p)==v for group in ('code_hashes','input_hashes') for p,v in freeze[group].items())
    (ART/'calls').mkdir();start=time.monotonic();events=[];original=provider._post
    report={'kind':'grounded_reasoning_development','status':'incomplete','variants':{},'independent_final':'PENDING','external_spend_usd':0}
    def observed(url,body,timeout,*args,**kwargs):
        if urlparse(url).hostname not in ('localhost','127.0.0.1','::1'):raise ValueError('Local only')
        left=120-(time.monotonic()-start)
        if left<=0:raise ValueError('Global local experiment time limit reached')
        if url.endswith('/chat/completions'):
            if len(events)>=12:raise ValueError('Global actual generation cap reached')
            event={'sequence':len(events)+1,'started_seconds':time.monotonic()-start,'request_hash':digest(body)};events.append(event)
            dump(ART/f'calls/{len(events):02d}-request.json',body)
            try:
                response=original(url,body,min(timeout,left),*args,**kwargs)
                dump(ART/f'calls/{event["sequence"]:02d}-response.json',response);event['usage']=response.get('usage');return response
            except Exception as exc:event['error_type']=type(exc).__name__;raise
            finally:event['finished_seconds']=time.monotonic()-start
        return original(url,body,min(timeout,left),*args,**kwargs)
    provider._post=observed
    try:
        for name in NAMES:
            cfg=read_config(BASE/name);tasks=load_benchmark(cfg);docs,chunks=scan_sources(cfg)
            cfg['_experiment_budget']=Budget({'max_model_calls_per_run':12-len(events),'max_run_seconds':max(.001,120-(time.monotonic()-start))})
            cfg['_partial_tasks']=[];rid=db.begin(cfg,'grounded_reasoning_validation',[]);calls_before=len(events)
            try:
                variant=evaluate_variant(cfg,tasks,chunks,[])
                checks=[];reviews=[]
                for t,row in zip(tasks,variant['tasks']):
                    row['reference_coverage']=evidence_coverage(t,row,chunks)
                    row['knowledge_manifest']={d['id']:d['fingerprint'] for d in docs};row['knowledge_version']=digest(row['knowledge_manifest'])
                    checks.append(inspect(t,row,chunks,cfg,digest({d['id']:d['fingerprint'] for d in docs}),builtin=True))
                    reviews.append(packet(sample_for(t,row,chunks,cfg,checks[-1]['sample']['source_version'])))
                entry={'run_id':rid,'actual_generation_attempts':len(events)-calls_before,'variant':variant,'checks':checks,'review_items':reviews}
                report['variants'][name]=entry;dump(ART/f'{name}.json',entry);db.finish(cfg,rid,entry)
            except Exception as exc:
                db.finish(cfg,rid,{'partial_tasks':cfg['_partial_tasks']},type(exc).__name__);raise
        report['status']='completed'
    except Exception as exc:report['error']={'type':type(exc).__name__,'message':str(exc)}
    finally:
        provider._post=original
        dump(ART/'execution-log.json',{'actual_generation_attempts':len(events),'events':events,'elapsed_seconds':time.monotonic()-start,
            'max_calls':12,'max_seconds':120,'external_spend_usd':0,'method':'Reserved at actual chat POST boundary including failures; tokenizer requests excluded'})
        dump(ART/'results.json',report)
    print(json.dumps({'status':report['status'],'calls':len(events),'seconds':time.monotonic()-start,'error':report.get('error')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);a=p.parse_args();prepare() if a.action=='prepare' else run()
