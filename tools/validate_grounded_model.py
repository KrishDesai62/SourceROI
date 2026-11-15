"""Grounded local smoke + two provisional semantic probes. Cap 6 calls/120s.

No prompt/label feedback loop. All results retained, human review remains pending.
"""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from examples.knowledge_change.demo import workspace
from sourceroi.live import assurance as a
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze
from sourceroi.live.validation import Budget
from sourceroi.live.provider import run_chat

root=Path('workspace/grounded-model-validation');out=Path('docs/artifacts/grounded-model-validation.json')
if root.exists() or out.exists():raise SystemExit('Refusing existing evidence paths')
reference=json.loads(Path('workspace/reliability-24/project.json').read_text());start=time.monotonic()
for name,days in [('source',30),('candidate',14)]:
    cfg=workspace(root/name,days=days);p=root/name/'project.json';obj=json.loads(p.read_text());obj['model']=reference['model']
    obj['local_inference_manifest']=reference['local_inference_manifest'];obj['settings'].update(max_model_calls_per_run=6,max_run_seconds=120,release_policy={'version':1,'name':'strict_grounded'})
    p.write_text(json.dumps(obj,indent=2))
    # Same questions and authoritative answers as the previous smoke; no label repair.
    tasks=[{'id':'returns','question':'How many days is the return period (returns_days)? Answer with only the number.','expected':'30','evidence':[{'document_id':'policy::returns.json','quote':'30'}]},
           {'id':'warranty','question':'How many days is warranty coverage (warranty_days)? Answer with only the number.','expected':'365','evidence':[{'document_id':'policy::warranty.json','quote':'365'}]}]
    (root/name/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks)+'\n')
freeze(read_config(root/'source'),root/'accepted');before=read_config(root/'accepted');after=read_config(root/'candidate')
intent={'expected_tasks':['returns'],'protected_tasks':['warranty'],'declared_by':'authored fixture owner','rationale':'Returns 30 to 14; warranty protected'}
spec=a.propose(before,after,intent=intent)
approval=a.review(spec,reviewer='authored fixture owner',rationale='Only returns intentionally changes',expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
report=a.execute(before,after,spec,approval=approval,max_calls=4,max_seconds=100,policy='strict_grounded')
probes=[];generation_calls=report['execution']['model_generation_calls']
for title,text in [('correct_support','Products may be returned within 14 days.'),('matching_number_wrong_topic','Warranty coverage lasts 14 days.')]:
    if generation_calls>=6 or time.monotonic()-start>=120:break
    budget=Budget({'max_model_calls_per_run':1,'max_run_seconds':max(.01,120-(time.monotonic()-start))})
    context=[{'id':'probe::evidence#chunk0','document_id':'probe::evidence','source_id':'probe','title':'Evidence','text':text}]
    cfg={**after,'_experiment_budget':budget,'settings':{**after['settings'],'release_policy':{'version':1,'name':'legacy_exact'}}}
    budget.before();generation_calls+=1
    try:
        answer=run_chat('Provisional semantic check: does this evidence support the claim that the return period is 14 days? Answer only supported, unsupported, or uncertain. This is not independent ground truth.',context,cfg)
        budget.after(answer);probes.append({'case':title,'result':answer,'authority':'provisional same-model judgment; never used as a release label or gate','uncertainty':'uncalibrated, no independent correctness assurance'})
    except Exception as exc:probes.append({'case':title,'error_type':type(exc).__name__,'authority':'unavailable; no ground truth'})
report['provisional_semantic_probes']=probes
report['sprint_budget']={'max_model_calls':6,'actual_model_calls':generation_calls,'max_seconds':120,'elapsed_seconds':time.monotonic()-start}
report['external_spend_usd']=0;report['independent_semantic_reviews']=0
out.write_text(json.dumps(report,indent=2)+'\n');out.with_suffix('.md').write_text(a.markdown(report))
print(json.dumps({'verdict':report['verdict'],'checks':report.get('check_statuses'),'budget':report['sprint_budget']},indent=2))
