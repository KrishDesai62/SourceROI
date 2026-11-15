"""Offline captured-output comparison and zero-model optimizer execution."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace/.deps'))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.policies import select_context
from sourceroi.live.evidence_contract import precheck
from sourceroi.live.validation import optimize
from sourceroi.live import facts,db
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'docs/artifacts/final-hardening'


def main():
    if (ART/'offline-comparison.json').exists():raise ValueError('Evidence exists')
    old=json.loads((ROOT/'docs/artifacts/grounded-reasoning/results.json').read_text());entries={}
    with patch('sourceroi.live.provider._post',side_effect=AssertionError('Offline comparison must not request inference')):
        for name,item in old['variants'].items():
            cfg=read_config(ROOT/'workspace/grounded-reasoning'/name);start=time.perf_counter();_,chunks=scan_sources(cfg)
            for task in load_benchmark(cfg):
                pool=precheck(task['question'],chunks,cfg,None,task.get('scope'))[0] if name!='fixed' else chunks
                select_context(task['question'],pool,{**cfg,'_calculation_contract':task.get('calculation_contract'),'_task_scope':task.get('scope')})
            processing_ms=1000*(time.perf_counter()-start);rows=item['variant']['tasks'];supported=[r for r in rows if r['id']!='missing_period']
            entries[name]={'origin':'Preserved captured development outputs, not fresh inference','task_count':4,
                'supported_correct':sum(r['correct'] for r in supported),'supported_n':3,'false_abstentions':sum(r['actual']=='INSUFFICIENT_EVIDENCE' for r in supported),
                'unsupported_answers':sum(r['actual']!='INSUFFICIENT_EVIDENCE' for r in rows if r['id']=='missing_period'),
                'invalid_citations':sum(len(r['invalid_citations']) for r in rows),'captured_generation_calls':item['actual_generation_attempts'],
                'captured_tokens':item['variant']['metrics']['total_tokens'],'captured_mean_task_latency_ms':item['variant']['metrics']['mean_latency_ms'],
                'current_offline_source_processing_ms_for_four_tasks':processing_ms,'independent_semantic_quality':None,
                'caveat':'Original global accounting failed and latency had test contention. Captured subset usage only; do not infer complete global tokens or causal runtime savings.'}
        original=ROOT/'workspace/final-hardening-numerics/financial_lookup';output=ROOT/'workspace/final-hardening-optimizer'
        if output.exists():raise ValueError('Optimizer destination exists')
        shutil.copytree(original,output)
        case=next(c for c in json.loads((ART/'numerical-frozen-cases.json').read_text())['cases'] if c['id']=='financial_lookup')
        cfg=json.loads((output/'project.json').read_text());cfg['settings'].update(max_model_calls_per_run=4,max_run_seconds=90,retrieval_policy={'name':'predicate'})
        (output/'project.json').write_text(json.dumps(cfg,indent=2))
        scope={'jurisdiction':'US','policy_scope':'synthetic'};task={'id':case['id'],'question':case['question'],'expected':case['expected'],'scoring':'numeric',
            'split':'development','scope':scope,'requires_grounding':True,'answer_contract':{'version':1,'type':'numeric'},
            'calculation_contract':case['contract'],'calculation_authorization':facts.authorize(case['question'],scope,case['contract'],reviewer='Codex development author',rationale='Frozen synthetic financial lookup, not independent human review')}
        (output/'benchmark.jsonl').write_text(json.dumps(task)+'\n');cfg=read_config(output);rid=db.begin(cfg,'optimization_validation',[])
        start=time.perf_counter();result=optimize(cfg,quality_floor=1,min_citation_rate=1,objective='token_budget',max_tasks=1,max_candidates=1);wall_ms=(time.perf_counter()-start)*1000
        db.finish(cfg,rid,result)
    (ART/'deterministic-optimizer.json').write_text(json.dumps({'run_id':rid,'report':result,'actual_generation_calls':0,'tokens':0,'wall_ms':wall_ms,'independent_quality':None},indent=2)+'\n')
    report={'captured_comparison':entries,'optimizer':{'status':result['status'],'deployment':result['deployment'],'decision':result['recommended']['decision'],
        'task_count':1,'actual_generation_calls':0,'tokens':0,'wall_ms':wall_ms,'comparison_scope':'One synthetic financial lookup using explicit source-calculation mode; not paired with prior model tasks'},
        'new_actual_model_calls':0,'external_spend_usd':0,'promotion':'NONE','independent_validation':'PENDING',
        'reference_status':'Prior narrow calculation successes are not independent validation; new numerical set fails 2/9 supported structures, so no broad reliable reference is established.'}
    (ART/'offline-comparison.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['optimizer'],indent=2))


if __name__=='__main__':main()
