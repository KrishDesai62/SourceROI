"""Summarize authored controls; do not infer customer benefit or independent accuracy."""
import json
from pathlib import Path
import sys
source=Path(sys.argv[1]);out=Path(sys.argv[2])
if out.exists():raise SystemExit('Refusing to overwrite evidence')
r=json.loads(source.read_text());rows=r['scenarios'];metrics={}
for name,m in r['confusion_matrices'].items():
    metrics[name]={'consequential_scenarios_blocked':m['BLOCK']['BLOCK'],'consequential_scenarios':sum(m['BLOCK'].values()),
        'legitimate_updates_false_blocked':m['ACCEPT']['BLOCK'],'legitimate_updates':sum(m['ACCEPT'].values()),
        'review_verdicts':sum(v['REVIEW'] for v in m.values()),'inconclusive_verdicts':sum(v['INCONCLUSIVE'] for v in m.values()),
        'equivalent_agent_task_executions':sum(s['evaluation_calls'][name] for s in rows)}
roots={'protected_regression':'policy::warranty.json','outdated_policy':'policy::returns.json',
       'essential_removed':'policy::returns.json','contradiction':'policy::aa_new.json','multi_source':'policy::warranty.json',
       'correct_without_support':'policy::returns.json','new_content_new_dependency':'policy::aa_new.json'}
localization=[]
for s in rows:
    if s['scenario'] not in roots:continue
    candidates=[t['candidate_causes'] for t in s['report']['tasks'] if not t['candidate_correct'] or t['evidence_loss']]
    truth=roots[s['scenario']]
    localization.append({'scenario':s['scenario'],'authored_document_cause':truth,
        'top1':any(cs and cs[0]==truth for cs in candidates),'top3':any(truth in cs[:3] for cs in candidates)})
summary={'source':str(source),'validation_level':r['validation_level'],'methods':metrics,
    'actual_shared_and_workflow_callback_task_executions':r['actual_callback_task_executions'],
    'model_inference_calls':0,'new_ground_truth_independently_reviewed':False,'human_review_time_saved':None,
    'proposals':{'count':sum(s['proposed_update_count'] for s in rows),'matching_authored_decisions':sum(s['proposed_updates_matching_authored_oracle'] for s in rows),
                 'known_incorrect':sum(s['known_incorrect_proposals'] for s in rows),'unknown_intent':sum(s['unknown_intent_proposals'] for s in rows)},
    'selector_missed_affected_tasks':{m:sum(len(s['missed_affected_tasks'][m]) for s in rows) for m in ('SourceROI','D_reference_selection')},
    'source_roi_full_suite_calls_avoided':0,'source_roi_execution_wall_seconds':sum(s['report']['execution']['wall_seconds'] for s in rows),
    'all_comparator_wall_seconds':sum(s['wall_seconds_including_all_comparators'] for s in rows),
    'localization':{'authored_single_document_cases':len(localization),'top1':sum(s['top1'] for s in localization),'top3':sum(s['top3'] for s in localization),
        'cases':localization,'excluded':'Ranking case changes both configuration and content; not a source-only causal claim.'},
    'repair':{'controlled_trials':sum(s['repair_verified'] is not None for s in rows),'registered_suite_restored':sum(s['repair_verified'] is True for s in rows)},
    'limits':r['limitations']}
out.write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
