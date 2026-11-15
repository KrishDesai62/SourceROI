"""Audit preserved as-executed model evidence; never rewrite the raw report."""
import hashlib
import json
from pathlib import Path
import sys


def main(source,output):
    source=Path(source);output=Path(output)
    if output.exists():raise ValueError('Accounting audit exists')
    report=json.loads(source.read_text());observed=[];flags=[]
    for row in report['cases']:
        result=row.get('model_result',{})
        generated=result.get('answer_origin')=='model' or result.get('raw_response') is not None
        if generated:observed.append(row['case']['id'])
        if generated!=row.get('model_generated'):flags.append({'case':row['case']['id'],'reported_model_generated':row.get('model_generated'),'observed_model_generated':generated})
    actual=len(observed);recorded=report['budget']['calls'];planned=report['budget']['max_calls']
    result={'kind':'evidence_experiment_accounting_audit','raw_report':str(source),'raw_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'recorded_generation_calls':recorded,'actual_generation_responses':actual,'planned_cap':planned,
        'planned_cap_exceeded':actual>planned,'user_sprint_cap':12,'user_sprint_cap_respected':actual<=12,
        'mismatched_generation_flags':flags,'actual_generated_cases':observed,
        'reported_tokens_recomputed':sum(r.get('model_result',{}).get('input_tokens',0)+r.get('model_result',{}).get('output_tokens',0) for r in report['cases']),
        'elapsed_seconds':report['budget']['elapsed_seconds'],'user_seconds_cap':120,
        'cause':'The empty-context raw control bypassed the precheck and called the provider, but the harness reserved/counts a model call only when context was nonempty.',
        'fix':'Strict provider now refuses empty-context generation even with a cached control trace. Future harness explicitly returns software abstention before reservation for empty context. No model rerun was made.',
        'interpretation':'Raw output metrics include all 11 model responses. The raw model_generated_only subset and recorded call counter are incorrect for the empty row; use this audit. Contract-assisted outputs are replay/postprocessing, not extra inference or demonstrated independent grounding.',
        'external_spend_usd':0,'remaining_model_budget_not_used':12-actual}
    output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result

if __name__=='__main__':main(sys.argv[1],sys.argv[2])
