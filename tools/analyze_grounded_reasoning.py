"""No-inference analysis and strict-release replays for grounded reasoning.

Recorded outputs are replayed, never relabeled as new inference. Controlled
mutations are explicit. No synthetic review is represented as independent human
validation; real strict ACCEPT remains unavailable without required reviewers.
"""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace/.deps'))
from tools.validate_grounded_reasoning import ROOT,ART,BASE,dump,sha,REVIEWER
from sourceroi.live import assurance as a
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,load_benchmark
from sourceroi.live.data_ci import freeze,digest
from sourceroi.live.grade import wilson_interval
from tools.analyze_real_world_e2e import conventional


def main():
    results=json.loads((ART/'results.json').read_text());ledger=json.loads((ART/'execution-log.json').read_text());summary={};reviews=[]
    for name,entry in results['variants'].items():
        rows=entry['variant']['tasks'];supported=[r for r in rows if r['id']!='missing_period'];negative=next(r for r in rows if r['id']=='missing_period')
        correct=sum(r['correct'] for r in supported)
        summary[name]={'supported_correct':correct,'supported_n':len(supported),'supported_ci95':wilson_interval(correct,len(supported)),
            'lookup_correct':next(r['correct'] for r in rows if r['id']=='depreciation_lookup'),
            'arithmetic_correct':sum(r['correct'] for r in rows if r['id'].endswith('difference')),'arithmetic_n':2,
            'false_abstentions':sum(r['actual']=='INSUFFICIENT_EVIDENCE' for r in supported),'unsupported_factual_answers':int(negative['actual']!='INSUFFICIENT_EVIDENCE'),
            'unsupported_question_n':1,'unsupported_origin':negative['answer_origin'],
            'full_retrieved_reference_coverage':sum(r['reference_coverage']==1 for r in supported),
            'full_cited_reference_coverage':sum(c['cited_reference_coverage']==1 for r,c in zip(rows,entry['checks']) if r['id']!='missing_period'),
            'invalid_citation_ids':sum(len(r['invalid_citations']) for r in rows),'independent_semantic_correctness':None,'independent_citation_correctness':None,
            'generation_attempts':entry['actual_generation_attempts'],'prompt_tokens':entry['variant']['metrics']['provider_reported_prompt_tokens'],
            'completion_tokens':entry['variant']['metrics']['provider_reported_completion_tokens'],'total_tokens':entry['variant']['metrics']['total_tokens'],
            'mean_task_latency_ms':entry['variant']['metrics']['mean_latency_ms'],
            'development_reference_rule_pass':correct==len(supported) and negative['correct'] and all(r['reference_coverage']==1 for r in supported) and not any(r['invalid_citations'] for r in rows),
            'independent_reference_qualified':False,'incomplete_tasks':4-len(rows),
            'answers':[{k:r[k] for k in ('id','actual','correct','answer_origin')} for r in rows]}
        reviews+=entry['review_items']
    dump(ART/'pending-semantic-reviews.json',{'kind':'external_release_review_packet','independently_reviewed':False,'items':reviews,
        'instructions':'Real external operator/reviewers adjudicate exact claim spans, supporting citations, applicability and stale facts. Calculation mode is distinct from model output. No independent final labels are present.'})
    # Strict no-change release on frozen source-calculation input, replaying its
    # already recorded results. No historical source workspace is changed.
    work=BASE/'release-replay';shutil.copytree(BASE/'source_calculation',work,ignore=shutil.ignore_patterns('.sourceroi'))
    cfg=read_config(work);freeze(cfg,BASE/'release-accepted');before=read_config(BASE/'release-accepted');after=read_config(work)
    tasks=load_benchmark(cfg);intent={'expected_tasks':[],'protected_tasks':[t['id'] for t in tasks],
        'declared_by':REVIEWER,'rationale':'Development no-change release replay only; no human or production authorization'}
    spec=a.propose(before,after,intent=intent)
    approval=a.review(spec,reviewer=REVIEWER,rationale='Technical development review protects all frozen tasks; no independent semantic approval',protected_tasks=intent['protected_tasks'])
    dump(ART/'replay-spec.json',spec);dump(ART/'replay-technical-review.json',approval)
    entry=results['variants']['source_calculation'];variant=entry['variant']
    def callback(cfg,questions):
        result=deepcopy(variant);wanted={q['id'] for q in questions};result['tasks']=[r for r in result['tasks'] if r['id'] in wanted];return result
    with patch('sourceroi.live.provider._post',side_effect=AssertionError('Replay must not generate')):
        review=a.execute(before,after,spec,approval=approval,callback=callback,max_calls=8,policy='strict_grounded',persist=False)
        def wrong(cfg,questions):
            result=callback(cfg,questions)
            if cfg['_root']==after['_root']:
                for row in result['tasks']:
                    if row['id']=='depreciation_lookup':row.update(answer='34',actual='34',raw_answer=34)
            return result
        blocked=a.execute(before,after,spec,approval=approval,callback=wrong,max_calls=8,policy='strict_grounded',persist=False)
        incomplete=a.execute(before,after,spec,approval=approval,callback=callback,max_calls=7,policy='strict_grounded',persist=False)
    assert review['verdict']=='REVIEW' and blocked['verdict']=='BLOCK' and incomplete['verdict']=='INCONCLUSIVE'
    dump(ART/'strict-review-replay.json',review);dump(ART/'strict-block-controlled-mutation.json',blocked);dump(ART/'strict-inconclusive-replay.json',incomplete)
    dump(ART/'release-states.json',{'REVIEW':{'observed':review['verdict'],'origin':'Recorded deterministic answer replay; absent human reviews and negative-reference coverage stay unresolved'},
        'BLOCK':{'observed':blocked['verdict'],'origin':'Explicitly controlled 33-to-34 output mutation, not a real model response'},
        'INCONCLUSIVE':{'observed':incomplete['verdict'],'origin':'Bounded preflight with insufficient logical task cap; zero generation'},
        'ACCEPT':{'real_independent_release':'PENDING','automated_fixture_test':'tests/test_grounded_release.py::test_strict_accept_requires_bound_explicit_review','note':'Synthetic test validates required review behavior; not actual independent human approval.'},'new_generation_attempts':0})
    # Maintained comparisons keep all earlier authorized facts/checks and traces.
    old=ROOT/'docs/artifacts/irs-e2e';old_release=json.loads((old/'release.json').read_text())
    b=read_config(ROOT/'workspace/irs-e2e/accepted');c=read_config(ROOT/'workspace/irs-e2e/candidate')
    annotations={r['id']:r for r in json.loads((old/'frozen-annotations.json').read_text())['annotations']};arms={}
    for name in ('maintained_full_suite','maintained_with_diff'):
        r=conventional(b,c,old_release,annotations)
        arms[name]={'verdict':r['verdict'],'wall_ms':r['wall_ms'],'task_rows_checked':6,'additional_model_calls':0,
            'human_edits':None,'human_review_actions':None,'active_human_seconds':None,
            'ordinary_diff_trace_packet':'../engineering-sprint/baseline-b-diffs-and-traces.json' if name=='maintained_with_diff' else None,
            'conditions':r['conditions']}
    oldspec=json.loads((old/'change-plan-v2.json').read_text());oldreview=json.loads((old/'technical-development-review-v2.json').read_text())
    def oldcallback(cfg,questions):return deepcopy(old_release['baseline' if cfg['_root']==b['_root'] else 'candidate'])
    start=time.perf_counter()
    with patch('sourceroi.live.provider._post',side_effect=AssertionError('Replay must not generate')):
        r=a.execute(b,c,oldspec,approval=oldreview,callback=oldcallback,max_calls=12,policy='strict_grounded',persist=False)
    arms['sourceroi']={'verdict':r['verdict'],'wall_ms':1000*(time.perf_counter()-start),'logical_task_rows_executed':12,'additional_model_calls':0,
        'maintenance_counters':r['maintenance'],'human_edits':None,'human_review_actions':None,'active_human_seconds':None}
    dump(ART/'three-arm-comparison.json',{'arms':arms,'tie':len({v['verdict'] for v in arms.values()})==1,
        'limitation':'Same outputs/approved facts. Maintained checks share primitives, not independent implementations. Checker-only A/B inspect six candidate rows; SourceROI replays twelve before/after rows with extra bookkeeping; timings are not normalized labor/performance comparisons.'})
    # Same conditions can also inspect the new contract modes: no review bypass.
    dump(ART/'summary.json',{'variants':summary,'strict_states':{'review':review['verdict'],'controlled_block':blocked['verdict'],'incomplete':incomplete['verdict'],'real_accept':'PENDING'},
        'total_generation_attempts':ledger['actual_generation_attempts'],'reported_total_tokens':sum(e.get('usage',{}).get('total_tokens',0) for e in ledger['events']),
        'experiment_elapsed_seconds':ledger['elapsed_seconds'],'external_spend_usd':0,'independent_final':'PENDING',
        'human_study':'PENDING','optimization':'Not expanded: no independently reliable model reference; calculation mode remains a separate contract-bound development result.'})
    print(json.dumps({'summary':summary,'strict_states':[review['verdict'],blocked['verdict'],incomplete['verdict']],'arms':arms},indent=2))


if __name__=='__main__':main()
