"""Single predeclared adversarial development run. At most 10 calls / 120 seconds.

Raw model outputs and owner-contract precheck results are separate. Applying the
screen to observed outputs is replay, not a second inference or independent truth.
"""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.provider import run_chat
from sourceroi.live.validation import Budget
from sourceroi.live.evidence_contract import precheck,abstention
from sourceroi.live.answer_contract import check
from sourceroi.live.data_ci import digest

NUM={'version':1,'type':'numeric'}
ALIASES={'version':1,'subject_aliases':[['return','returns','returned','sent back']]}
Q='How many days is the return period? Answer with only the number, or INSUFFICIENT_EVIDENCE if unsupported.'
CASES=[
 {'id':'exposed_warranty_only','group':'previously_exposed','texts':['Warranty coverage lasts 14 days.'],'expected':'INSUFFICIENT_EVIDENCE'},
 {'id':'exposed_numeric_support','group':'previously_exposed','texts':['Products may be returned within 14 days.'],'expected':'14'},
 {'id':'fresh_correct_id_wrong_content','group':'authored_development','texts':['Warranty coverage lasts 21 days.'],'expected':'INSUFFICIENT_EVIDENCE'},
 {'id':'fresh_missing_essential','group':'authored_development','texts':[],'expected':'INSUFFICIENT_EVIDENCE'},
 {'id':'fresh_expired','group':'authored_development','texts':['Products may be returned within 30 days under the historical policy.'],'metadata':{'jurisdiction':'US','effective_to':'2020-01-01'},'scope':{'jurisdiction':'US','as_of':'2026-11-13'},'expected':'INSUFFICIENT_EVIDENCE'},
 {'id':'fresh_wrong_jurisdiction','group':'authored_development','texts':['EU customers may return products within 30 days.'],'metadata':{'jurisdiction':'EU','effective_from':'2025-01-01'},'scope':{'jurisdiction':'US','as_of':'2026-11-13'},'expected':'INSUFFICIENT_EVIDENCE'},
 {'id':'fresh_conflicting_policies','group':'authored_development','texts':['Products may be returned within 14 days.','Products may be returned within 30 days.'],'expected':'INSUFFICIENT_EVIDENCE'},
 {'id':'fresh_paraphrase_declared_alias','group':'authored_development','texts':['Items may be sent back within a fortnight.'],'expected':'14'},
 {'id':'fresh_multiple_plausible_citations','group':'authored_development','texts':['Products may be returned within 21 days.','The return period for this policy is 21 days.'],'expected':'21'},
 {'id':'fresh_premise_not_permitted','group':'authored_development','texts':['Returns are not permitted. There is no return period.'],'expected':'INSUFFICIENT_EVIDENCE'},
 {'id':'fresh_incomplete_alias_contract','group':'authored_development','texts':['Items may be sent back within a fortnight.'],'aliases':{'version':1,'subject_aliases':[['return','returns']]},'expected':'14'}]


def metrics(rows,key):
    total=len(rows);valid=[r for r in rows if r['case']['expected']!='INSUFFICIENT_EVIDENCE'];unsupported=[r for r in rows if r['case']['expected']=='INSUFFICIENT_EVIDENCE']
    result=lambda r:r[key]
    return {'cases':total,'matches_authored_expectation':sum(result(r)['answer']==r['case']['expected'] for r in rows),
        'unsupported_factual_answers':sum(result(r)['answer']!='INSUFFICIENT_EVIDENCE' for r in unsupported),
        'unsupported_cases':len(unsupported),'abstentions_on_unsupported':sum(result(r)['answer']=='INSUFFICIENT_EVIDENCE' for r in unsupported),
        'false_abstentions_on_authored_supported_cases':sum(result(r)['answer']=='INSUFFICIENT_EVIDENCE' for r in valid),
        'supported_cases':len(valid),'invalid_citation_ids':sum(len(result(r).get('invalid_citations',[])) for r in rows),
        'answer_type_violations':sum(not result(r).get('answer_contract_valid',False) for r in rows),
        'independently_reviewed_semantic_accuracy':None}


def main():
    out=Path('docs/artifacts/evidence-abstention-validation.json');plan=Path('docs/artifacts/evidence-abstention-plan.json')
    if out.exists() or plan.exists():raise SystemExit('Refusing existing experiment destinations')
    plan.write_text(json.dumps({'cases':CASES,'max_calls':10,'max_seconds':120,'answer_contract':NUM,
        'evidence_contract':ALIASES,'method':'Raw generation without declared alias guard; postcheck/replay uses explicit owner requirements. Labels are authored engineering controls, not independent validation.'},indent=2)+'\n')
    cfg=read_config('workspace/grounded-model-validation/candidate')
    budget=Budget({'max_model_calls_per_run':10,'max_run_seconds':120});rows=[];start=time.monotonic()
    for case in CASES:
        context=[{'id':f'policy::{case["id"]}-{i}.txt#chunk0','document_id':f'policy::{case["id"]}-{i}.txt','source_id':'policy','title':'Evidence','text':text,**case.get('metadata',{})} for i,text in enumerate(case['texts'])]
        raw_cfg={**cfg,'_answer_contract':NUM,'_evidence_contract':case.get('aliases',ALIASES),'_task_scope':case.get('scope'),'_grounding_precheck':{'abstain':False,'mode':'raw_model_control_screen_bypassed_explicitly','entailment':'unverified'},'_require_citations':True,'_experiment_budget':budget}
        try:
            if context:
                budget.before();raw=run_chat(Q,context,raw_cfg);budget.after(raw)
            else:
                _,empty_trace=precheck(Q,[],cfg)
                raw=abstention(empty_trace,cfg)
        except Exception as exc:
            rows.append({'case':case,'error_type':type(exc).__name__});continue
        _,trace=precheck(Q,context,cfg,case.get('aliases',ALIASES),case.get('scope'))
        guarded=abstention(trace,cfg) if trace['abstain'] else {**raw,'grounding_precheck':trace,'answer_origin':'observed_model_output_reused_no_second_call'}
        rows.append({'case':case,'context':context,'model_result':raw,'contract_assisted_result':guarded,
            'source_evidence_version':digest(context),'model_generated':bool(context),
            'strict_release_eligible':False,'strict_reason':'Independent semantic/abstention adjudication unavailable; no strict grounded ACCEPT asserted'})
    complete=[r for r in rows if 'model_result' in r]
    report={'kind':'evidence_abstention_development','independent_validation':False,'plan_sha256':digest(json.loads(plan.read_text())),
        'cases':rows,'raw_output_metrics':metrics(complete,'model_result'),'contract_assisted_metrics':metrics(complete,'contract_assisted_result'),
        'model_generated_only_metrics':metrics([r for r in complete if r['model_generated']],'model_result'),
        'stratified':{g:{'raw':metrics([r for r in complete if r['case']['group']==g],'model_result'),'assisted':metrics([r for r in complete if r['case']['group']==g],'contract_assisted_result')} for g in ('previously_exposed','authored_development')},
        'budget':{'calls':budget.calls,'max_calls':10,'elapsed_seconds':time.monotonic()-start,'max_seconds':120},
        'reported_tokens':sum(r['model_result'].get('input_tokens',0)+r['model_result'].get('output_tokens',0) for r in complete),
        'observed_model_latency_ms':sum(r['model_result']['model_latency_ms'] for r in complete),
        'assisted_generation_calls_if_screened_first':sum(not r['contract_assisted_result']['grounding_precheck']['abstain'] for r in complete),
        'actual_new_calls_avoided':0,'actual_independent_human_reviews':0,'external_spend_usd':0,
        'limitations':['Software abstention is not improved model reasoning','Alias completeness is an owner responsibility and can cause false rejection','Numeric-shaped conflict check is not general contradiction reasoning','Raw empty-context row is software abstention, not a model response','Reused outputs are replay; no measured deployment cost advantage','No hidden final/independent customer data']}
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('raw_output_metrics','contract_assisted_metrics','budget','reported_tokens')},indent=2))

if __name__=='__main__':main()
