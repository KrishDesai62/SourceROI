"""Summarize raw evidence plus the explicit accounting correction, no inference."""
import hashlib
import json
from pathlib import Path
import sys
base=Path('docs/artifacts');out=Path(sys.argv[1])
if out.exists():raise SystemExit('Output exists')
load=lambda n:json.loads((base/n).read_text())
r=load('evidence-abstention-validation.json');audit=load('evidence-abstention-accounting-audit.json');fair=load('grounded-reliability-maintained-baselines.json')
assert hashlib.sha256((base/'evidence-abstention-validation.json').read_bytes()).hexdigest()==audit['raw_sha256']
rows=[x for x in r['cases'] if 'model_result' in x]
summary={'kind':'grounded_reliability_realworld_validation_summary','raw_experiment_sha256':audit['raw_sha256'],
 'actual_generation_calls':audit['actual_generation_responses'],'recorded_counter':audit['recorded_generation_calls'],
 'planned_limit_exceeded':audit['planned_cap_exceeded'],'user_12_call_limit_respected':audit['user_sprint_cap_respected'],
 'reported_tokens':audit['reported_tokens_recomputed'],'elapsed_seconds':audit['elapsed_seconds'],
 'mean_model_latency_ms':sum(x['model_result']['model_latency_ms'] for x in rows)/len(rows),
 'raw_output_metrics_correct_denominator_all_11_generated':r['raw_output_metrics'],'contract_screen_replay_metrics':r['contract_assisted_metrics'],
 'cited_responses':sum(bool(x['model_result']['citations']) for x in rows),'invalid_citation_ids':sum(len(x['model_result']['invalid_citations']) for x in rows),
 'model_supported_case_answer_successes':sum(x['model_result']['answer']==x['case']['expected'] for x in rows if x['case']['expected']!='INSUFFICIENT_EVIDENCE'),
 'supported_cases':sum(x['case']['expected']!='INSUFFICIENT_EVIDENCE' for x in rows),
 'no_claim_of_actual_guarded_generation_savings':True,'hypothetical_calls_if_screened_first':r['assisted_generation_calls_if_screened_first'],
 'strict_release_interpretation':'Inline probes did not execute the full release pipeline. Independent semantics/provenance are not established; no grounded approval is asserted. Required review/format gates are verified separately in unit tests.',
 'fair_combined_baseline_tie':fair['confusion_matrices']['C_maintained_full_suite']==fair['confusion_matrices']['E_SourceROI'],
 'fair_matrices':fair['confusion_matrices'],'source_owner_pilot':'Template and no-inference preparation tool ready; real owner data/approval not supplied',
 'human_study':'pending real participants','independent_final_labels':False,'semantic_entailment_accuracy':None,
 'post_run_fixes':'Empty-context cached-trace bypass and harness accounting fixed; numeric/string prompt conflict removed and alias OR clarified. These post-run fixes were not rerun on the model.',
 'external_spend_usd':0,'commercial_advantage':'not established'}
assert summary['actual_generation_calls']==11 and summary['reported_tokens']==4174 and summary['supported_cases']==4
assert summary['fair_combined_baseline_tie']
out.write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'actual_calls':11,'supported_answer_successes':summary['model_supported_case_answer_successes'],'supported_cases':4,'fair_tie':True,'summary':str(out)},indent=2))
