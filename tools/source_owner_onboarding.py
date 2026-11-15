"""Materialize source-owner input into existing SourceROI workflows. No inference.

Owner identity/independence are declarations, not authenticated by this tool.
Authoritative decisions remain explicit inputs; no model generates labels.
"""
import argparse
from datetime import datetime,timezone,date
import json
from pathlib import Path
import re
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import load_benchmark
from sourceroi.live.data_ci import freeze,digest
from sourceroi.live.answer_contract import validate as validate_answer,check as check_answer
from sourceroi.live.evidence_contract import validate as validate_evidence


def template():
    return {'version':1,'status':'awaiting_real_source_owner','owner':'','labels_established_at':'','labels_from_evaluated_model':False,
        'before_documents':[],'after_documents':[],'tasks':[],
        'document_schema':{'source_id':'policy','name':'returns.txt','text':'','metadata':{'authority':'','jurisdiction':'US','policy_scope':'online','effective_from':'2025-01-01'}},
        'task_schema':{'id':'returns','question':'','expected_before':'','expected_after':'','intended_change':True,
            'answer_contract':{'version':1,'type':'numeric'},'evidence_contract':{'version':1,'subject_aliases':[['return','returns','returned','sent back']]},
            'scope':{'jurisdiction':'US','as_of':'2026-11-13','policy_scope':'online'},'evidence_before':[{'document_id':'policy::returns.txt','quote':''}],
            'evidence_after':[{'document_id':'policy::returns.txt','quote':''}]},
        'instructions':'Real source owner supplies documents and labels established before outputs. This is a pilot bundle, not an independently validated final set. Inspect proposals and explicitly approve review decisions.'}


def materialize(bundle,output):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Choose a new output; existing data is immutable')
    if bundle.get('version')!=1 or not isinstance(bundle.get('owner'),str) or not bundle['owner'].strip() or bundle.get('labels_from_evaluated_model') is not False:raise ValueError('Named owner and independent label provenance declaration required')
    try:when=datetime.fromisoformat(bundle['labels_established_at'].replace('Z','+00:00'))
    except (KeyError,ValueError,TypeError):raise ValueError('Pre-established label timestamp required')
    if when.tzinfo is None or when>datetime.now(timezone.utc):raise ValueError('Invalid label timestamp')
    versions={};metadata={}
    for version in ('before','after'):
        records=bundle.get(version+'_documents')
        if not isinstance(records,list) or not records or len(records)>50:raise ValueError('Provide 1..50 documents per version')
        versions[version]={};metadata[version]={}
        for doc in records:
            if not re.fullmatch('[a-z][a-z0-9_-]*',str(doc.get('source_id',''))) or not re.fullmatch(r'[a-zA-Z0-9_-]+\.txt',str(doc.get('name',''))):raise ValueError('Use safe source IDs and .txt basenames')
            if not isinstance(doc.get('text'),str) or not doc['text'].strip() or len(doc['text'])>100000:raise ValueError('Invalid document text')
            sid=doc['source_id'];ident=sid+'::'+doc['name']
            if ident in versions[version]:raise ValueError('Duplicate document identity')
            meta=doc.get('metadata',{})
            if not isinstance(meta,dict) or set(meta)-{'authority','jurisdiction','policy_scope','effective_from','effective_to','scope'} or any(not isinstance(v,str) for v in meta.values()):raise ValueError('Invalid source metadata')
            for field in ('effective_from','effective_to'):
                if meta.get(field):date.fromisoformat(meta[field])
            if sid in metadata[version] and metadata[version][sid]!=meta:raise ValueError('Separate sources for differing document scope/authority metadata')
            metadata[version][sid]=meta;versions[version][ident]=doc
    tasks=bundle.get('tasks')
    if not isinstance(tasks,list) or not tasks or len(tasks)>6:raise ValueError('Provide 1..6 tasks for the paired 12-call pilot')
    ids=set();benchmark=[];expected={};refs={};protected=[]
    for task in tasks:
        tid=task.get('id')
        if not isinstance(tid,str) or not tid or tid in ids:raise ValueError('Unique task IDs required')
        ids.add(tid)
        if type(task.get('intended_change')) is not bool:raise ValueError('Explicit intended_change required')
        for key in ('question','expected_before','expected_after'):
            if not isinstance(task.get(key),str) or not task[key].strip():raise ValueError('Missing authoritative question/expectations')
        validate_answer(task.get('answer_contract'));validate_evidence(task.get('evidence_contract'))
        for version in ('before','after'):
            value=task['expected_'+version]
            if task.get('answer_contract',{}).get('type')=='structured' and value!='INSUFFICIENT_EVIDENCE':
                try:value=json.loads(value)
                except ValueError:raise ValueError('Structured expected labels must be JSON strings')
            if not check_answer(value,task.get('answer_contract'))[0]:raise ValueError('Authoritative expectation violates declared response type; correct the contract/label explicitly')
        for version in ('before','after'):
            evidence=task.get('evidence_'+version)
            if not isinstance(evidence,list):raise ValueError('Supporting evidence labels must be lists')
            if not evidence and (task.get('expected_'+version)!='INSUFFICIENT_EVIDENCE' or not isinstance(task.get('absence_rationale_'+version),str) or not task['absence_rationale_'+version].strip()):raise ValueError('Missing evidence needs an explicit abstention label and absence rationale')
            for ref in evidence:
                doc=versions[version].get(ref.get('document_id'))
                if doc is None or not isinstance(ref.get('quote'),str) or not ref['quote'].strip() or ref['quote'] not in doc['text']:raise ValueError('Evidence quote/version mismatch')
        if task['intended_change']:expected[tid]=task['expected_after'];refs[tid]=task['evidence_after']
        else:
            if task['expected_before']!=task['expected_after']:raise ValueError('Protected behavior cannot have an unapproved changed expectation')
            protected.append(tid)
        benchmark.append({'id':tid,'question':task['question'],'expected':task['expected_before'],'evidence':task['evidence_before'],
            'requires_grounding':True,'scoring':task.get('scoring','structured_exact' if task.get('answer_contract',{}).get('type')=='structured' else 'exact'),**{k:task[k] for k in ('answer_contract','evidence_contract','scope') if k in task},
            **({'behavior_constraint':'protected'} if not task['intended_change'] else {})})
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='owner-onboard-') as directory:
        staging=Path(directory)/'bundle';staging.mkdir()
        for version,folder in [('before','source'),('after','candidate')]:
            root=staging/folder;root.mkdir();sources=[]
            for sid,meta in metadata[version].items():
                (root/'sources'/sid).mkdir(parents=True)
                sources.append({'id':sid,'name':sid,'path':'sources/'+sid,**meta})
            for doc in versions[version].values():(root/'sources'/doc['source_id']/doc['name']).write_text(doc['text'])
            cfg={'id':'owner-pilot','name':'Source-owner grounded pilot','runner':'rag_chat','benchmark':'benchmark.jsonl',
                'model':{'name':'qwen2.5-1.5b-instruct-q4_k_m','base_url':'http://127.0.0.1:8788/v1','local_only':True,'runtime':'llama_cpp','context_tokenizer':'llama_cpp','compact_source_ids':True,'seed':1729,'temperature':0,'max_output_tokens':384,'timeout_seconds':60},
                'settings':{'max_chunks':5,'chunk_chars':1100,'overlap_chars':100,'max_model_calls_per_run':12,'max_run_seconds':120,'release_policy':{'version':1,'name':'strict_grounded'}},'sources':sources}
            (root/'project.json').write_text(json.dumps(cfg,indent=2));(root/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in benchmark)+'\n')
            load_benchmark(read_config(root))
        freeze(read_config(staging/'source'),staging/'accepted')
        (staging/'intent.json').write_text(json.dumps({'expected_tasks':list(expected),'protected_tasks':protected,'declared_by':bundle['owner'],'rationale':'Source-owner declared knowledge update; expected labels not model generated'},indent=2)+'\n')
        (staging/'review-decisions-DRAFT.json').write_text(json.dumps({'reviewer':bundle['owner'],'rationale':'DRAFT: inspect source changes and proposals before explicitly approving','expected_changes':expected,'protected_tasks':protected,'expected_evidence':refs},indent=2)+'\n')
        manifest={'kind':'source_owner_pilot','bundle_sha256':digest(bundle),'owner_declaration':bundle['owner'],'labels_established_at':bundle['labels_established_at'],
            'independence':'Operator declaration only; not authenticated or independent final validation','model_calls':0,'approval_status':'DRAFT; change-review not executed'}
        (staging/'onboarding.json').write_text(json.dumps(manifest,indent=2)+'\n');staging.replace(output)
    return {'output':str(output),'tasks':len(benchmark),'model_calls':0,'review_status':'pending explicit approval'}

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    t=sub.add_parser('template');t.add_argument('--output',type=Path,required=True)
    r=sub.add_parser('prepare');r.add_argument('--input',type=Path,required=True);r.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.command=='template':
        if args.output.exists():raise SystemExit('Output exists')
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(template(),indent=2)+'\n');print('Pending real source-owner input; no labels or model results created')
    else:
        if args.input.stat().st_size>6000000:raise SystemExit('Bundle exceeds 6 MB limit')
        print(json.dumps(materialize(json.loads(args.input.read_text()),args.output),indent=2))
