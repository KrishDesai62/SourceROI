"""Reproducible sprint summary from preserved raw results; no new inference."""
import argparse
import hashlib
import json
from pathlib import Path
from tools.release_review_packet import score


def main(output):
    base=Path('docs/artifacts');output=Path(output)
    if output.exists():raise ValueError('Summary already exists')
    load=lambda name:json.loads((base/name).read_text())
    old=load('knowledge-local-smoke.json');new=load('knowledge-local-smoke-repaired.json')
    fair=load('validation-sprint-fair-comparison.json');external=load('external-rag-validation.json')
    semantic=load('semantic-citation-validation.json');pending=score(load('validation-sprint-smoke-reviews.json'),[])
    methods={}
    for m,matrix in fair['confusion_matrices'].items():
        methods[m]={'blocking_detected':matrix['BLOCK']['BLOCK'],'blocking_total':sum(matrix['BLOCK'].values()),
            'legitimate_false_blocks':matrix['ACCEPT']['BLOCK'],'legitimate_total':sum(matrix['ACCEPT'].values()),
            'review':sum(v['REVIEW'] for v in matrix.values()),'inconclusive':sum(v['INCONCLUSIVE'] for v in matrix.values()),
            'equivalent_task_executions':sum(s['methods'][m]['equivalent_task_executions'] for s in fair['scenarios']),
            'missed_affected_task_occurrences':sum(len(s['methods'][m]['missed_affected_task_ids']) for s in fair['scenarios']),
            'answer_fields_without_prefill':sum(s['methods'][m]['manual_expected_answer_text_edits'] for s in fair['scenarios'])}
    model=lambda r:{'verdict':r['verdict'],'calls':r['execution']['calls'],'seconds':r['execution']['wall_seconds'],
        'tokens':sum(r[s]['metrics']['total_tokens'] for s in ('baseline','candidate')),
        'baseline_correct':sum(t['baseline_correct'] for t in r['tasks']),
        'reviewed_candidate_correct':sum(t['candidate_correct'] for t in r['tasks']),
        'missing_citation_responses':sum(not t['citations'] for s in ('baseline','candidate') for t in r[s]['tasks'])}
    old_manifest=json.loads(Path('workspace/knowledge-local-smoke/accepted/snapshot.json').read_text())['manifest']
    new_manifest=json.loads(Path('workspace/knowledge-local-smoke-repaired/accepted/snapshot.json').read_text())['manifest']
    result={'kind':'validation_differentiation_sprint_summary','old_smoke':model(old),'repaired_smoke':model(new),
        'original_smoke_sha256':hashlib.sha256((base/'knowledge-local-smoke.json').read_bytes()).hexdigest(),
        'same_original_labels':old['versions']['test_set_version']==new['versions']['test_set_version'],
        'same_model_generation_settings':old['execution_identity']['candidate_model']==new['execution_identity']['candidate_model'],
        'same_baseline_document_fingerprints':old_manifest==new_manifest,'methods':methods,'full_confusion_matrices':fair['confusion_matrices'],
        'same_full_suite_and_source_roi_confusion':fair['confusion_matrices']['C_maintained_full_suite']==fair['confusion_matrices']['E_SourceROI'],
        'prefill_review':{'suggestions':sum(s['suggestions']['review_items'] for s in fair['scenarios']),
            'known_bad':sum(s['suggestions']['known_incorrect'] for s in fair['scenarios']),
            'unknown_intent':sum(s['suggestions']['unknown_intent'] for s in fair['scenarios']),
            'actual_human_corrections':None,'actual_human_time_saved':None},
        'measured_scopes_ms':{'paired_application_shared_across_A_to_D':sum(s['paired_application_ms'] for s in fair['scenarios']),
            'D_selector_only':sum(s['strong_selector_ms'] for s in fair['scenarios']),
            'E_full_orchestration_and_application':sum(s['source_roi_whole_workflow_ms'] for s in fair['scenarios']),
            'limitation':'Different timed scopes; no normalized wall-clock superiority conclusion'},
        'external_demo':{'verdicts':[r['verdict'] for r in external['release_results']],
            'requests':external['actual_http_requests'],'seconds':external['elapsed_seconds'],
            'unknown_version_rejected':external['unknown_version_rejected'],'authorship':external['validation_level']},
        'semantic':{'authored_integrity_controls':len(semantic['items']),'real_outputs_awaiting_review':pending['total'],
            'independent_completed_reviews':pending['completed'],'semantic_accuracy':None,'citation_entailment_accuracy':None,'reliability_verdict':pending['verdict']},
        'independent_final_evaluation':'Not available; external annotation protocol remains pending',
        'new_real_model_calls':new['execution']['calls'],'external_spend_usd':0,'commercial_advantage':'Not established'}
    assert result['same_original_labels'] and result['same_model_generation_settings'] and result['same_baseline_document_fingerprints']
    assert result['same_full_suite_and_source_roi_confusion'] and new['execution']['calls']==4 and new['execution']['wall_seconds']<60
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'summary':str(output),'fair_full_suite_ties_source_roi':True,'semantic_status':pending['verdict']},indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
