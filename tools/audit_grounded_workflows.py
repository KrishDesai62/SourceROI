"""Equal-authority before/after checker replay; no new model requests/human acts."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace/.deps'))
from tools.validate_grounded_reasoning import ART,BASE,ROOT,dump
from sourceroi.live import assurance as a
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.release_policy import inspect
from sourceroi.live.grade import grade
from sourceroi.live.answer_contract import check


def maintained(before,after,report,spec,approval):
    start=time.perf_counter();a.verify_snapshot(before);rows={};results=[]
    for stage,cfg in [('baseline',before),('candidate',after)]:
        _,chunks=scan_sources(cfg);actual={r['id']:r for r in report[stage]['tasks']}
        for original in load_benchmark(cfg):
            task=deepcopy(original)
            if stage=='candidate' and task['id'] in approval.get('expected_changes',{}):
                task['expected']=approval['expected_changes'][task['id']]
                task['accepted_answers']=[task['expected']]
                task['evidence']=approval.get('expected_evidence',{}).get(task['id'],[])
            row=deepcopy(actual[task['id']]);row['answer']=row.get('answer',row.get('actual'))
            raw=row['answer'] if row['answer']=='INSUFFICIENT_EVIDENCE' else row.get('raw_answer',row['answer'])
            fmt,_=check(raw,task.get('answer_contract'));correct=grade(row['answer'],task) and fmt and row.get('response_complete',True)
            checks=inspect(task,row,chunks,cfg,spec[stage+'_sources'],builtin=False)
            block=not correct or any(checks[k]=='BLOCK' for k in ['citation_status','scope_status','relevance_status','numeric_evidence_status'])
            verdict='BLOCK' if block else 'INCONCLUSIVE' if checks['version_status']=='INCONCLUSIVE' else 'REVIEW'
            results.append({'stage':stage,'task_id':task['id'],'correct':correct,'verdict':verdict,'checks':checks})
            rows[(stage,task['id'])]=correct
    candidate=[r for r in results if r['stage']=='candidate']
    verdict='BLOCK' if any(r['verdict']=='BLOCK' for r in candidate) else 'INCONCLUSIVE' if any(r['verdict']=='INCONCLUSIVE' for r in candidate) else 'REVIEW'
    return {'verdict':verdict,'task_rows_checked':len(results),'results':results,'wall_ms':1000*(time.perf_counter()-start),
        'lost_tasks':[r['task_id'] for r in candidate if rows[('baseline',r['task_id'])] and not r['correct']],
        'new_generation_attempts':0,'new_tokens':0,'actual_human_edits':None,'human_review_actions':None,'active_human_seconds':None}


def main():
    old=ROOT/'docs/artifacts/irs-e2e';release=json.loads((old/'release.json').read_text())
    cases=[('historical_real_regression',read_config(ROOT/'workspace/irs-e2e/accepted'),read_config(ROOT/'workspace/irs-e2e/candidate'),
        release,json.loads((old/'change-plan-v2.json').read_text()),json.loads((old/'technical-development-review-v2.json').read_text())),
        ('new_calculation_no_change',read_config(BASE/'release-accepted'),read_config(BASE/'release-replay'),json.loads((ART/'strict-review-replay.json').read_text()),
         json.loads((ART/'replay-spec.json').read_text()),json.loads((ART/'replay-technical-review.json').read_text()))]
    outcomes={}
    with patch('sourceroi.live.provider._post',side_effect=AssertionError('No inference during workflow audit')):
        for name,b,c,report,spec,approval in cases:
            arms={arm:maintained(b,c,report,spec,approval) for arm in ['maintained_full_suite','maintained_with_diff']}
            def callback(cfg,questions):return deepcopy(report['baseline' if cfg['_root']==b['_root'] else 'candidate'])
            start=time.perf_counter();integrated=a.execute(b,c,spec,approval=approval,callback=callback,max_calls=2*len(load_benchmark(b)),policy='strict_grounded',persist=False)
            arms['sourceroi']={'verdict':integrated['verdict'],'task_rows_checked':integrated['execution']['calls'],
                'wall_ms':1000*(time.perf_counter()-start),'new_generation_attempts':0,'new_tokens':0,
                'maintenance':integrated['maintenance'],'actual_human_edits':None,'human_review_actions':None,'active_human_seconds':None}
            assert len({r['verdict'] for r in arms.values()})==1
            outcomes[name]={'arms':arms,'tie':True,'equivalent_factual_authority':True,
                'baseline_b_diffs_and_traces':'docs/artifacts/engineering-sprint/baseline-b-diffs-and-traces.json' if name=='historical_real_regression' else 'No source change; both receive recorded contexts/manifests'}
    dump(ART/'maintained-full-suite-audit.json',{'cases':outcomes,'prior_counter_correction':'Historical sprint artifacts labeled conventional checks as 12 executions, but its conventional function inspected six candidate rows. This audit actually checks all before/after rows (12 historical, 8 new) for both A/B. Historical artifacts are unchanged. Detection tie remains.',
        'limits':'All use shared deterministic primitives and equal missing independent-review requirements; checker implementations are not independent. Timings include different orchestration work/cache state and do not measure labor.'})
    print(json.dumps({n:{arm:(v['verdict'],v['task_rows_checked']) for arm,v in case['arms'].items()} for n,case in outcomes.items()}))


if __name__=='__main__':main()
