"""Replay scheduling over the same recorded maintained checks; zero new model calls.

Early BLOCK can stop work; passing release still needs all remaining tasks and
strict semantic checks. This is not a measured inference/cost optimization win.
"""
import json
from pathlib import Path
import sys
source=Path(sys.argv[1]);out=Path(sys.argv[2])
if out.exists():raise SystemExit('Output exists')
data=json.loads(source.read_text());rows=[]
for scenario in data['scenarios']:
    report=scenario['source_roi'];ids=[r['id'] for r in scenario['scored_tasks']]
    risky=[r['task_id'] for r in report['specification']['impact'] if r['potentially_affected']]
    rest=[i for i in ids if i not in risky];negative=rest[:2];remaining=rest[2:]
    order=risky+negative+remaining
    failures={r['id'] for r in scenario['scored_tasks'] if not r['correct'] or r['coverage'] is not None and r['coverage']<1} if scenario['authoritative_approval'] else set()
    executed=[]
    for ident in order:
        executed.append(ident)
        if ident in failures:break
    blocked=bool(set(executed)&failures)
    rows.append({'case':scenario['scenario'],'stages':{'deterministic_screen':'source/intent/trace diff, no model calls','high_risk':risky,'negative_controls':negative,'remaining_before_accept':remaining},
        'selected_affected_recall':len(set(risky)&set(scenario['all_affected_task_ids']))/len(scenario['all_affected_task_ids']) if scenario['all_affected_task_ids'] else None,
        'missed_failure_ids':sorted(failures-set(order)),'replay_execution_order':executed,'replay_equivalent_calls':2*len(executed),
        'full_suite_equivalent_calls':2*len(ids),'verdict':'BLOCK' if blocked else scenario['methods']['C_maintained_full_suite']['verdict'],
        'unexecuted_after_early_block':sorted(set(ids)-set(executed)),'strict_semantic_review':'Still required; replay verdict uses aligned legacy check policy only'})
result={'kind':'staged_workflow_replay','actual_new_model_calls':0,'actual_new_agent_calls':0,'cases':rows,
    'replay_equivalent_calls':sum(r['replay_equivalent_calls'] for r in rows),'full_suite_equivalent_calls':sum(r['full_suite_equivalent_calls'] for r in rows),
    'missed_failures':sum(len(r['missed_failure_ids']) for r in rows),'false_blocks':sum(r['verdict']=='BLOCK' and s['oracle']=='ACCEPT' for r,s in zip(rows,data['scenarios'])),
    'limitation':'Exposed authored fixtures; replay logical calls, not actual measured inference savings. A maintained conventional runner can use the same ordering/early rejection. Full-suite/mandatory remaining checks still required before strict ACCEPT.'}
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('replay_equivalent_calls','full_suite_equivalent_calls','missed_failures','false_blocks')},indent=2))
