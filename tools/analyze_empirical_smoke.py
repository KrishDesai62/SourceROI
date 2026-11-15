"""Read-only evaluation of the two actual accounting-smoke answers; no inference."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources
from sourceroi.live.release_policy import inspect
from sourceroi.live.diagnosis import diagnose
from sourceroi.live.grade import grade
from tools.run_empirical_experiment import check_freeze,conventional,dump


def analyze(benchmark,smoke,output):
    benchmark=Path(benchmark).resolve();smoke=Path(smoke).resolve();check_freeze(benchmark)
    annotations=json.loads((benchmark/'frozen-labels.json').read_text())['annotations']
    plan=json.loads((benchmark/'change-plan.json').read_text());observed=[]
    for version,year,key in [('accepted',2024,'baseline_sources'),('candidate',2025,'candidate_sources')]:
        sample=json.loads((smoke/(version+'-business.json')).read_text())
        task=deepcopy(sample['task']);label=next(a for a in annotations if a['version']==year and a['task_id']=='business')
        task.update(expected=label['expected'],evidence=[{'document_id':'current::notice.pdf','quote':label['quote']}])
        cfg=read_config(benchmark/version);_,chunks=scan_sources(cfg);row=sample['row']
        t0=time.perf_counter();grounding=inspect(task,row,chunks,cfg,plan[key],builtin=False)
        source_ms=(time.perf_counter()-t0)*1000
        t0=time.perf_counter();ordinary=conventional(cfg,[task],[row],{'business':sample['retrieved_evidence']})
        conventional_ms=(time.perf_counter()-t0)*1000
        observed.append({'version':year,'question':task['question'],'expected':task['expected'],'actual':row['actual'],
            'answer_correct':grade(row['actual'],task),'source_roi_observed_answer_check':'PASS' if grade(row['actual'],task) else 'BLOCK',
            'source_roi_strict_evidence_checks':grounding,'conventional_observed_subset':ordinary,
            'source_roi_literal_failure':not grade(row['actual'],task),'diagnosis':diagnose(task,row,chunks,cfg),
            'correct_source_quote':label['quote'],'correct_quote_is_in_retrieved_context':any(label['quote'] in c['text'] for c in sample['retrieved_evidence']),
            'medical_21_in_retrieved_context':any('21 cents per mile' in c['text'] for c in sample['retrieved_evidence']),
            'source_roi_evidence_inspection_ms':source_ms,'ordinary_checks_ms':conventional_ms,
            'prompt_tokens':row.get('prompt_tokens'),'completion_tokens':row.get('completion_tokens'),
            'model_latency_ms':row.get('model_latency_ms'),'raw_answer_json':row.get('raw_response')})
    # Feed only the two actual traces to the complete strict workflow. It must
    # reject missing remaining tasks, rather than synthesize answers for them.
    from sourceroi.live.assurance import execute
    def partial_actual_trace(cfg,tasks):
        version='accepted' if Path(cfg['_root'])==benchmark/'accepted' else 'candidate'
        data=json.loads((smoke/(version+'-business.json')).read_text())
        return {'tasks':[deepcopy(data['row'])],'metrics':{},'adapter_identity':'Actual smoke trace replay; other tasks not executed'}
    incomplete=execute(read_config(benchmark/'accepted'),read_config(benchmark/'candidate'),plan,
        approval=None,callback=partial_actual_trace,max_calls=20,max_seconds=90,policy='strict_grounded',persist=False)
    incomplete['analysis_scope']='Partial replay of 2 captured real answers; no model generation in this analysis. Existing execution.calls is requested logical slots, not actual native generation count.'
    if incomplete['verdict']!='INCONCLUSIVE':raise ValueError('Incomplete smoke trace must not become a complete strict release')
    dump(Path(output).with_name(Path(output).stem+'-incomplete-strict-release.json'),incomplete)
    result={'kind':'READ_ONLY_ACTUAL_SMOKE_ANALYSIS','model_calls_in_this_analysis':0,'actual_smoke_calls':2,
        'supported_correct':sum(r['answer_correct'] for r in observed),'supported_n':2,
        'false_abstentions':sum(r['actual']=='INSUFFICIENT_EVIDENCE' for r in observed),
        'unsupported_questions_executed':0,'unsupported_rejection_rate':None,
        'source_roi_observed_failures':sum(r['source_roi_literal_failure'] for r in observed),
        'conventional_observed_failures':sum(r['conventional_observed_subset']['verdict']=='BLOCK' for r in observed),
        'detection_result':'TIE on the two observed answer failures; no differentiated coverage demonstrated',
        'source_roi_incomplete_workflow':incomplete['verdict'],'full_release_status':'INCONCLUSIVE_NOT_EXECUTED: nine questions/version unexecuted; no deployment verdict claimed',
        'independent_semantic_review':None,'human_maintenance_effort':None,'observations':observed,
        'root_cause_hypothesis':'Correct business-rate evidence was retrieved but model selected the medical rate 21 and cited all passages. JSON shape/citation membership do not establish claim support. Mechanistic cause unproven; no additional ablation authorized.'}
    dump(output,result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('benchmark','smoke','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(analyze(a.benchmark,a.smoke,a.output),indent=2))
