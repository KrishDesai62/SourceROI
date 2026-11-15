"""Two-call check of final grammar's safe abstention branch; no favorable reruns."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.provider import run_chat
from sourceroi.live.validation import Budget
out=Path('docs/artifacts/grounded-abstention-validation.json')
if out.exists():raise SystemExit('Output exists')
previous=json.loads(Path('docs/artifacts/grounded-model-validation.json').read_text())
remaining=120-previous['sprint_budget']['elapsed_seconds']
if previous['sprint_budget']['actual_model_calls']+2>12 or remaining<=0:raise SystemExit('Sprint inference budget exhausted')
budget=Budget({'max_model_calls_per_run':2,'max_run_seconds':min(30,remaining)})
cfg={**read_config('workspace/grounded-model-validation/candidate'),'_experiment_budget':budget,'_require_citations':True}
plan=[{'case':'support_available','text':'Products may be returned within 14 days.','intended_answer':'14'},
      {'case':'irrelevant_matching_number','text':'Warranty coverage lasts 14 days.','intended_answer':'INSUFFICIENT_EVIDENCE'}]
Path('docs/artifacts/grounded-abstention-plan.json').write_text(json.dumps({'cases':plan,'max_calls':2,'max_seconds':min(30,remaining),'authority':'Authored branch-validation controls, not independently labeled'},indent=2)+'\n')
start=time.monotonic();rows=[]
for item in plan:
    context=[{'id':'policy::probe.txt#chunk0','document_id':'policy::probe.txt','source_id':'policy','title':'Evidence','text':item['text']}]
    budget.before()
    try:
        result=run_chat('How many days is the return period? Answer with only the number, or INSUFFICIENT_EVIDENCE if unsupported.',context,cfg)
        budget.after(result);rows.append({'case':item,'result':result,'matches_authored_intent':result['answer']==item['intended_answer']})
    except Exception as exc:rows.append({'case':item,'error_type':type(exc).__name__})
report={'kind':'grounded_abstention_branch_validation','cases':rows,'actual_calls':budget.calls,'elapsed_seconds':time.monotonic()-start,
 'sprint_total_calls':previous['sprint_budget']['actual_model_calls']+budget.calls,
 'sprint_combined_experiment_seconds':previous['sprint_budget']['elapsed_seconds']+time.monotonic()-start,
 'independently_reviewed':False,'semantic_release_authority':False,'external_spend_usd':0}
out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'total_calls':report['sprint_total_calls'],'cases':[(r['case']['case'],r.get('result',{}).get('answer'),r.get('matches_authored_intent')) for r in rows]},indent=2))
