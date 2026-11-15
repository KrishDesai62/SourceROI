"""Fixed bounded analytical operations using the existing parser supervisor.

Worker inputs are source data, public configuration and proposed intent only.
Authenticated principals, receipts, semantic judgments and security writes stay
in the parent. No callable or arbitrary import name is a wire operation.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
from . import parser_boundary as boundary

PURE={'search','precheck','coverage','policy','diagnose','knowledge_measure','knowledge_history'}
SOURCE={'inventory','diagnose','plan'}


def execute(operation,p):
    if operation=='knowledge_history':
        from .engine import compare_variants
        return [compare_variants(p['variants'][0],v) for v in p['variants'][1:]]
    if operation=='knowledge_measure':
        from .knowledge_decision import measure_worker
        return measure_worker(p)
    if operation=='search':
        from .retrieve import _search_in_process
        return _search_in_process(p['question'],p['chunks'],p['k'])
    if operation=='precheck':
        from .evidence_contract import _precheck_in_process
        return _precheck_in_process(p['question'],p['chunks'],p['cfg'],p['contract'],p['scope'])
    if operation=='coverage':
        from .data_ci import _evidence_coverage_in_process
        return _evidence_coverage_in_process(p['task'],p['row'],p['chunks'])
    if operation=='policy':
        from .policies import _select_context_in_process
        return _select_context_in_process(p['question'],p['chunks'],p['cfg'])
    if operation=='inventory':
        from .assurance import _inventory_in_process
        return _inventory_in_process(p['cfg'])
    if operation=='diagnose':
        from .diagnosis import _diagnose_in_process
        return _diagnose_in_process(p['task'],p['row'],p['chunks'],p.get('cfg'),calculation=p.get('calculation'))
    if operation=='plan':
        from .assurance import _propose_in_process
        return _propose_in_process(p['baseline'],p['candidate'],history=p['history'],intent=p['intent'])
    raise ValueError('Unsupported analytical operation')


def active():
    from .ingest import _WORKER_ACTIVE
    return _WORKER_ACTIVE


def public(cfg):
    return {k:deepcopy(v) for k,v in cfg.items() if not k.startswith('_') or k in ('_config_hash','_calculation_contract','_task_scope')}


def call(operation,**payload):
    if operation not in PURE:raise ValueError('Not a fixed pure analytical operation')
    chunks=payload.get('chunks',[])
    if not isinstance(chunks,list) or len(chunks)>50000 or any(not isinstance(c,dict) or not isinstance(c.get('id'),str) or not isinstance(c.get('text'),str) for c in chunks):raise ValueError('Invalid bounded analytical chunks')
    if len({c['id'] for c in chunks})!=len(chunks):raise ValueError('Analytical chunk identities must be unique')
    result=boundary.run({'operation':'analysis','analysis':operation,'payload':payload},{})
    if operation in ('search','policy','precheck'):
        if operation!='search' and (not isinstance(result,list) or len(result)!=2 or not isinstance(result[1],dict)):raise ValueError('Invalid analytical trace contract')
        if operation=='precheck' and result[1].get('entailment')!='unverified':raise ValueError('Analytical screen cannot assert semantic verification')
        selected=result if operation=='search' else result[0]
        if not isinstance(selected,list):raise ValueError('Invalid analytical selection result')
        known={c['id']:c for c in chunks}
        for c in selected:
            if c.get('id') not in known or any(c.get(k)!=v for k,v in known[c['id']].items() if k!='score') or set(c)-set(known[c['id']])-{'score'}:raise ValueError('Analytical selection changed registered evidence')
        if any('score' in c and (type(c['score']) not in (int,float) or not math.isfinite(c['score'])) for c in selected):raise ValueError('Invalid analytical score')
        if operation=='policy' and result[1].get('selected_ids')!=[c['id'] for c in selected]:raise ValueError('Analytical trace identity mismatch')
        if len({c['id'] for c in selected})!=len(selected):raise ValueError('Duplicate analytical selection')
    if operation=='coverage' and result is not None and (type(result) not in (int,float) or not 0<=result<=1):raise ValueError('Invalid reference coverage result')
    return result


def prepare(cfg,prefix,files):
    root,source_files,_,_=boundary.prepare(cfg)
    from .config import secure_path
    for name in (cfg.get('benchmark','benchmark.jsonl'),'snapshot.json'):
        path=root/name
        if path.exists():source_files[name]=boundary.snapshot(secure_path(root,name),root)
    for name,record in source_files.items():files[prefix+'/'+name]=record
    worker=public(cfg);worker['_root']=str(Path('input')/prefix)
    return worker,list(source_files.values()),root


@boundary.limited
def source(operation,cfg,**payload):
    if operation not in SOURCE-{'plan'}:raise ValueError('Invalid source analytical operation')
    files={};worker,records,root=prepare(cfg,'source',files)
    result=boundary.run({'operation':'analysis','analysis':operation,'payload':{**payload,'cfg':worker}},files,protected_root=root)
    boundary.verify(records,root)
    return result


@boundary.limited
def plan(baseline,candidate,history,intent):
    # Independently load control-plane labels in an operation with no source
    # documents. Never rely on a source-analysis worker to grant protected intent.
    from .ingest import load_benchmark
    from .data_ci import digest
    from .assurance import configuration,validate_spec,verify_snapshot
    verify_snapshot(baseline)
    tasks=load_benchmark(baseline)
    if digest(tasks)!=digest(load_benchmark(candidate)):raise ValueError('Authoritative benchmark must remain unchanged; revisions belong in reviewed proposals')
    requested=intent or {};ids={t['id'] for t in tasks}
    if not isinstance(requested,dict) or set(requested)-{'expected_tasks','protected_tasks','declared_by','rationale'}:raise ValueError('Invalid intent declaration')
    for field in ('expected_tasks','protected_tasks'):
        if not isinstance(requested.get(field,[]),list) or any(not isinstance(i,str) or i not in ids for i in requested.get(field,[])):raise ValueError('Unknown intent task')
    expected=set(requested.get('expected_tasks',[]));protected=set(requested.get('protected_tasks',[]))|{t['id'] for t in tasks if t.get('behavior_constraint')=='protected'}
    if expected&protected:raise ValueError('Conflicting intent declaration')
    if requested and any(not isinstance(requested.get(k),str) or not requested[k].strip() for k in ('declared_by','rationale')):raise ValueError('Intent requires declared_by and rationale')
    files={};old,old_records,old_root=prepare(baseline,'baseline',files);new,new_records,new_root=prepare(candidate,'candidate',files)
    result=boundary.run({'operation':'analysis','analysis':'plan','payload':{'baseline':old,'candidate':new,'history':history,'intent':intent}},files,protected_root=[baseline['_root'],candidate['_root']])
    boundary.verify(old_records,old_root);boundary.verify(new_records,new_root);validate_spec(result)
    if result['test_set_version']!=digest(tasks) or result['baseline_configuration']!=configuration(baseline) or result['candidate_configuration']!=configuration(candidate):raise ValueError('Analytical plan changed control-plane identities')
    normalized={**requested,'status':'declared_requires_review' if requested else 'unknown','expected_tasks':sorted(expected),'protected_tasks':sorted(protected)}
    if result['intent']!=normalized or {r['task_id'] for r in result['impact']}!=ids:raise ValueError('Analytical worker changed trusted intent/task identities')
    gold={t['id']:t['expected'] for t in tasks}
    for row in result['evaluation_proposals']:
        if row['task_id'] not in ids or row['old_expected']!=gold[row['task_id']] or row.get('status')!='pending' or row.get('requires_review') is not True:raise ValueError('Analytical proposal cannot grant review authority')
        if row['task_id'] in protected and (row['classification']!='PROTECTED_UNCHANGED' or row['suggested_expected'] is not None):raise ValueError('Analytical worker changed protected behavior')
    if set(result)-{'id','version','kind','evidence_proposals','baseline_sources','candidate_sources','baseline_configuration','candidate_configuration','test_set_version','potential_conflicts','changes','impact','evaluation_proposals','proposal_version','candidate_tests','intent','limitations'}:raise ValueError('Unexpected authority field in analytical plan')
    return result
