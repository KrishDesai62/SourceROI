"""Aggregate preserved grounding experiments, keeping judgments/metrics separate."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.maintenance import summarize
out=Path(sys.argv[1])
if out.exists():raise SystemExit('Output exists')
base=Path('docs/artifacts');load=lambda n:json.loads((base/n).read_text())
old=load('knowledge-local-smoke-repaired.json');new=load('grounded-model-validation.json');abstain=load('grounded-abstention-validation.json')
props=load('proposal-v2-final-validation.json');fair=load('grounding-final-fair-comparison.json');rag=load('document-rag-validation.json');staged=load('grounding-final-staged-replay.json')
def measurement(report):
    rows=[t for s in ('baseline','candidate') for t in report[s]['tasks']]
    return {'exact_baseline':sum(t['baseline_correct'] for t in report['tasks']),'exact_reviewed_candidate':sum(t['candidate_correct'] for t in report['tasks']),
        'responses':len(rows),'with_citations':sum(bool(t['citations']) for t in rows),'invalid_citations':sum(len(t['invalid_citations']) for t in rows),
        'model_calls':report['execution'].get('model_generation_calls',report['execution']['calls']),
        'tokens':sum(report[s]['metrics']['total_tokens'] for s in ('baseline','candidate')),
        'mean_task_latency_ms':sum(report[s]['metrics']['mean_latency_ms'] for s in ('baseline','candidate'))/2,
        'verdict':report['verdict']}
provisional=[{'case':p['case'],'answer':p.get('result',{}).get('answer'),'uncertainty':p['uncertainty']} for p in new['provisional_semantic_probes']]
maintenance={k:sum(s['source_roi']['maintenance'][k] for s in fair['scenarios']) for k in ('proposed_changes','accepted_suggestions','rejected_suggestions','manual_correction_fields','manual_answer_entry_fields','ambiguous_items','new_tests_proposed','protected_expectations_preserved')}
result={'kind':'reliability_grounding_sprint_summary','old_smoke':measurement(old),'new_grounded_smoke':measurement(new),
    'same_original_labels':old['versions']['test_set_version']==new['versions']['test_set_version'],
    'tokens_increase_percent':100*(measurement(new)['tokens']/measurement(old)['tokens']-1),
    'grounded_smoke_scope':'No task scope was supplied in the original-style numeric smoke; scope PASS means no configured mismatch, not independently verified dates/jurisdiction.',
    'abstention_controls':abstain,'provisional_semantic_judgments':provisional,'independent_human_semantic_reviews':0,
    'actual_sprint_model_calls':abstain['sprint_total_calls'],'combined_experiment_seconds':abstain['sprint_combined_experiment_seconds'],
    'actual_sprint_reported_tokens':sum(new[s]['metrics']['total_tokens'] for s in ('baseline','candidate'))+sum(p.get('result',{}).get('input_tokens',0)+p.get('result',{}).get('output_tokens',0) for p in new['provisional_semantic_probes'])+sum(p.get('result',{}).get('input_tokens',0)+p.get('result',{}).get('output_tokens',0) for p in abstain['cases']),
    'proposal_accuracy_authored_controls':props['summary'],'fair_matrices':fair['confusion_matrices'],
    'maintained_full_suite_tie':fair['confusion_matrices']['C_maintained_full_suite']==fair['confusion_matrices']['E_SourceROI'],
    'maintenance_field_counts':maintenance,'human_study':summarize('workspace/grounding-human-study.jsonl'),
    'staged_replay':{'full_equivalent_calls':staged['full_suite_equivalent_calls'],'replay_equivalent_calls':staged['replay_equivalent_calls'],'missed_failures':staged['missed_failures'],'false_blocks':staged['false_blocks'],'measured_inference_savings':None},
    'document_rag':{'verdicts':[r['verdict'] for r in rag['releases']],'requests':rag['actual_http_requests'],'ranking_drift_rejected':rag['ranking_drift_rejected'],'unknown_version_rejected':rag['unknown_version_rejected'],'authorship':rag['authorship']},
    'external_spend_usd':0,'limitations':['All engineering scenarios authored/exposed, no independent final labels','No human effort/correction/time study','Same-model semantic probes are uncalibrated, one unrelated passage incorrectly judged supported','Final-schema controls included a numeric-format mismatch and failed abstention; no favorable rerun','No competitive or customer superiority established']}
assert result['same_original_labels'] and result['actual_sprint_model_calls']<=12 and result['combined_experiment_seconds']<120
assert result['maintained_full_suite_tie']
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('old_smoke','new_grounded_smoke','actual_sprint_model_calls','actual_sprint_reported_tokens','proposal_accuracy_authored_controls','maintenance_field_counts','document_rag')},indent=2))
