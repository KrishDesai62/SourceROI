"""Real IRS document validation through existing SourceROI infrastructure.

Source-derived labels and review are explicitly Codex development annotations,
not IRS/source-owner/human approval or independent semantic ground truth.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'workspace/.deps'))
from sourceroi.live import assurance as a,db
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze,digest,evidence_coverage
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.engine import evaluate_variant
from sourceroi.live.policies import select_context
from sourceroi.live.evidence_contract import precheck
from sourceroi.live.release_policy import inspect,resolve,finalize
from sourceroi.live.grade import grade
from sourceroi.live.validation import Budget

BASE=ROOT/'workspace/irs-e2e';ART=ROOT/'docs/artifacts/irs-e2e'
ANNOTATOR='Codex technical development annotation; not human, IRS or source-owner approval'
NUM={'version':1,'type':'numeric'}


def dump(path,value):
    path=Path(path)
    if path.exists():raise ValueError('Refusing to overwrite '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def quote(text,needle):
    if needle not in text:raise ValueError('Authoritative quote absent: '+needle)
    return needle


def taskset(text24,text25):
    business24=quote(text24,'67 cents per');business25=quote(text25,'70')
    med24=quote(text24,'21 cents per mile');med25=quote(text25,'21 cents per mile')
    charity24=quote(text24,'14 cents per mile');charity25=quote(text25,'14 cents per mile')
    questions=[
        ('business','In the CURRENT notice, what is the business standard mileage rate in cents per mile?', '67','70',[business24],[business25],['business']),
        ('medical','In the CURRENT notice, what is the standard mileage rate for medical care in cents per mile?','21','21',[med24],[med25],['medical']),
        ('charity','In the CURRENT notice, how many cents per mile apply to gratuitous services to a charitable organization?','14','14',[charity24],[charity25],['charitable']),
        ('business_paraphrase','According to the CURRENT notice, how many cents can a business trip claim per mile under the standard rate?','67','70',[business24],[business25],['business']),
        ('business_minus_charity','Using the CURRENT notice, what is the business rate minus the charitable rate, in cents per mile?','53','56',[business24,charity24],[business25,charity25],['business','charitable']),
        ('canadian_rate','What Canadian standard business mileage rate does this collection authorize, in cents per mile?','INSUFFICIENT_EVIDENCE','INSUFFICIENT_EVIDENCE',[],[],['business'])]
    tasks=[];annotations=[]
    for ident,q,before,after,refs24,refs25,subjects in questions:
        refs=lambda quotes:[{'document_id':'current::CURRENT notice.pdf','quote':s} for s in quotes]
        task={'id':ident,'question':q,'expected':before,'scoring':'numeric' if before!='INSUFFICIENT_EVIDENCE' else 'exact',
            'requires_grounding':True,'answer_contract':NUM,'evidence_contract':{'version':1,'subject_aliases':[[s] for s in subjects]},
            'scope':{'jurisdiction':'CA' if ident=='canadian_rate' else 'US','policy_scope':'IRS standard mileage schedule'},'evidence':refs(refs24)}
        tasks.append(task);annotations.append({'id':ident,'expected_before':before,'expected_after':after,'evidence_before':refs(refs24),'evidence_after':refs(refs25),
            'expected_behavior_change':before!=after,'annotation_origin':ANNOTATOR,'independently_reviewed':False})
    return tasks,annotations


def prepare():
    if (BASE/'source').exists() or ART.exists():raise ValueError('Experiment destinations exist')
    source=json.loads((BASE/'raw/provenance.json').read_text())
    text24=(BASE/'raw/notice-2024.txt').read_text();text25=(BASE/'raw/notice-2025.txt').read_text()
    tasks,annotations=taskset(text24,text25)
    model=json.loads((ROOT/'workspace/reliability-24/project.json').read_text())['model']
    for name,year in [('source',2024),('candidate',2025)]:
        root=BASE/name;(root/'sources/current').mkdir(parents=True)
        shutil.copy2(BASE/f'raw/notice-{year}.pdf',root/'sources/current/CURRENT notice.pdf')
        cfg={'id':'irs-e2e','name':'Historical IRS mileage notice assistant','runner':'rag_chat','benchmark':'benchmark.jsonl',
            'model':model,'settings':{'release_policy':{'version':1,'name':'strict_grounded'},'max_chunks':3,'chunk_chars':1100,'overlap_chars':150,'max_model_calls_per_run':12,'max_run_seconds':120,'max_tasks_per_run':6},
            'sources':[{'id':'current','name':f'IRS active edition {year}','path':'sources/current','authority':'Internal Revenue Service, irs.gov','jurisdiction':'US',
                'policy_scope':'IRS standard mileage schedule','effective_from':f'{year}-01-01','effective_to':f'{year+1}-01-01'}]}
        (root/'project.json').write_text(json.dumps(cfg,indent=2));(root/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks)+'\n')
        dump(root/'source-provenance.json',source)
    freeze(read_config(BASE/'source'),BASE/'accepted')
    before=read_config(BASE/'accepted');after=read_config(BASE/'candidate')
    expected={x['id']:x['expected_after'] for x in annotations if x['expected_behavior_change']}
    protected=[x['id'] for x in annotations if not x['expected_behavior_change']]
    intent={'expected_tasks':list(expected),'protected_tasks':protected,'declared_by':ANNOTATOR,'rationale':'Development comparison of publicly issued IRS notices only; no independent human/business approval or deployment authorization'}
    spec=a.propose(before,after,intent=intent);a.save_proposal(after,spec)
    dump(ART/'frozen-annotations.json',{'version':1,'frozen_at':datetime.now(timezone.utc).isoformat(),'tasks':tasks,'annotations':annotations,'authority':'Answers from official notices; questions/labels authored by Codex and not independently reviewed','original_benchmark_sha256':digest(load_benchmark(before))})
    dump(ART/'change-plan.json',spec);dump(ART/'intent.json',intent)
    draft={'reviewer':ANNOTATOR,'rationale':'DRAFT: must not authorize expectations','expected_changes':expected,'protected_tasks':protected,
        'expected_evidence':{x['id']:x['evidence_after'] for x in annotations if x['id'] in expected}}
    draft_rejected=False
    try:a.review(spec,**draft)
    except ValueError:draft_rejected=True
    # This is the actual technical development reviewer, not a fabricated human/source owner.
    technical={**draft,'rationale':'Codex source-quoted development expectation review only. IRS authoritative values checked; no independent human semantic review or production authorization.'}
    approval=a.review(spec,**technical);a.save_review(after,spec,approval)
    dump(ART/'technical-development-review.json',approval)
    preflight=[]
    for label,cfg in [('before',before),('after',after)]:
        docs,chunks=scan_sources(cfg)
        for task in load_benchmark(cfg):
            selected,_=select_context(task['question'],chunks,cfg);eligible,screen=precheck(task['question'],selected,cfg,task.get('evidence_contract'),task.get('scope'))
            preflight.append({'version':label,'task_id':task['id'],'retrieved_ids':[c['id'] for c in selected],'screen':screen})
    dump(ART/'preflight.json',{'draft_review_rejected':draft_rejected,'preflight':preflight,'model_calls':0})
    dump(ART/'plan.json',{'max_generation_requests':12,'max_inference_seconds':120,'source_provenance':source,'benchmark_sha256':digest(load_benchmark(before)),
        'annotations_sha256':digest(annotations),'comparison':'Equivalent maintained checks reuse exact same model outputs; no separate model advantage claim','primary_corpus':'Active edition only, full original PDF. Historical 2024 retained raw and used in explicit stale/conflicting-source controls.',
        'extra_calls':'One actual business-task current-document ablation and one top-k=1 comparison, only if budget remains','human_review':'None; technical development reviewer explicitly identified. Strict semantic requirements never waived.'})
    print(json.dumps({'tasks':len(tasks),'changed_documents':len(spec['changes']),'predicted_affected':sum(r['potentially_affected'] for r in spec['impact']),'preflight_abstentions':sum(r['screen']['abstain'] for r in preflight),'draft_rejected':draft_rejected},indent=2))


def run():
    import sourceroi.live.provider as provider
    if (ART/'release.json').exists():raise ValueError('Result exists')
    before=read_config(BASE/'accepted');after=read_config(BASE/'candidate')
    spec=json.loads((ART/'change-plan-v2.json').read_text());approval=json.loads((ART/'technical-development-review-v2.json').read_text())
    plan=json.loads((ART/'plan.json').read_text())
    assert digest(load_benchmark(before))==plan['benchmark_sha256']
    original=provider._post;events=[];start=time.monotonic()
    def observed_post(url,body,timeout,*args,**kwargs):
        if url.endswith('/chat/completions'):
            if len(events)>=12 or time.monotonic()-start>=120:raise RuntimeError('Global actual generation request cap reached')
            event={'sequence':len(events)+1,'url':url,'request_sha256':digest(body),'request':body,'started_seconds':time.monotonic()-start}
            events.append(event);dump(ART/f'calls/{event["sequence"]:02d}-request.json',event)
            try:
                response=original(url,body,min(timeout,max(.001,120-(time.monotonic()-start))),*args,**kwargs)
                dump(ART/f'calls/{event["sequence"]:02d}-response.json',response);event['usage']=response.get('usage');event['reported_model']=response.get('model');return response
            except Exception as exc:event['error_type']=type(exc).__name__;raise
            finally:event['finished_seconds']=time.monotonic()-start
        return original(url,body,min(timeout,max(.001,120-(time.monotonic()-start))),*args,**kwargs)
    provider._post=observed_post
    try:
        shared=Budget({'max_model_calls_per_run':12,'max_run_seconds':110})
        def rag_callback(cfg,questions):
            # Question-only production payload reaches the callback. Labels remain in
            # the evaluation engine and never enter the provider request.
            benchmark={t['id']:t for t in load_benchmark(cfg)}
            selected=[benchmark[q['id']] for q in questions]
            docs,chunks=scan_sources(cfg);manifest={d['id']:d['fingerprint'] for d in docs}
            result=evaluate_variant({**cfg,'_experiment_budget':shared},selected,chunks,[])
            if {d['id']:d['fingerprint'] for d in scan_sources(cfg)[0]}!=manifest:raise ValueError('Corpus changed during agent execution')
            for row in result['tasks']:
                row['knowledge_manifest']=manifest;row['knowledge_version']=digest(manifest)
            return result
        release=a.execute(before,after,spec,approval=approval,callback=rag_callback,max_calls=12,max_seconds=110,policy='strict_grounded')
        release['callback_adapter']='Existing SourceROI lexical RAG + local provider, invoked through question/contract callback; observed filesystem manifest, not an external customer agent'
        release['actual_model_requests_at_completion']=len(events)
        dump(ART/'release.json',release);(ART/'release.md').write_text(a.markdown(release))
        extras={};docs,chunks=scan_sources(after);task=load_benchmark(after)[0]
        for label,excluded,policy in [('remove_current_notice',['current'],None),('top_k_1',[],{'name':'top_k','k':1})]:
            if len(events)>=12 or time.monotonic()-start>=120:extras[label]={'status':'not_run_budget'};continue
            cfg={**after,'settings':{**after['settings'],**({'retrieval_policy':policy} if policy else {})},'_experiment_budget':Budget({'max_model_calls_per_run':12-len(events),'max_run_seconds':max(.001,120-(time.monotonic()-start))})}
            t=deepcopy(task);t['expected']='70';t['evidence']=approval['expected_evidence']['business']
            try:extras[label]=evaluate_variant(cfg,[t],chunks,excluded)
            except Exception as exc:extras[label]={'error_type':type(exc).__name__}
        try:
            from sourceroi.live.validation import optimize
            optimizer_cfg={**after,'settings':{**after['settings'],'max_model_calls_per_run':min(1,max(0,12-len(events)))}}
            extras['existing_optimizer']=optimize(optimizer_cfg,max_tasks=1,max_candidates=1)
        except ValueError as exc:extras['existing_optimizer']={'status':'not_executed_preflight','reason':str(exc),'actual_generation_requests':0}
        dump(ART/'actual-ablation-and-topk.json',extras)
    finally:
        provider._post=original
        dump(ART/'execution-log.json',{'actual_generation_requests':len(events),'events':events,'elapsed_seconds':time.monotonic()-start,'max_calls':12,'max_seconds':120,'external_spend_usd':0,'counter_method':'At actual chat POST boundary including failures, separate from logical task execution/reservations'})
    print(json.dumps({'verdict':release['verdict'],'checks':release.get('check_statuses'),'actual_requests':len(events),'seconds':time.monotonic()-start},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','run']);args=p.parse_args();prepare() if args.stage=='prepare' else run()
