"""Post-run diagnostics and comparison, not a policy-fitting step."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import load_benchmark,scan_sources
from sourceroi.live.data_ci import evidence_coverage
from tools.summarize_local_validation import grouped_accuracy_interval


def main():
    base=Path('docs/artifacts/reliability-local')
    r=json.loads(base.with_suffix('.json').read_text());cfg=read_config('workspace/reliability-24')
    tasks={t['id']:t for t in load_benchmark(cfg)};chunks=scan_sources(cfg)[1]
    final={e['name']:e['variant'] for e in r['experiments'] if e['partition']=='heldout'}
    original=final['original'];rows=[]
    for name,variant in final.items():
        metrics=variant['metrics'];coverages=[evidence_coverage(tasks[t['id']],t,chunks) for t in variant['tasks']]
        rows.append({'policy':name,**metrics,'new_failures':r['comparisons'][name]['lost_tasks'],
            'recoveries':r['comparisons'][name]['gained_tasks'],'mean_reference_quote_coverage':sum(coverages)/len(coverages),
            'complete_reference_tasks':sum(x==1 for x in coverages),
            'correct_without_context':sum(t['correct'] and not t['retrieved_chunk_ids'] for t in variant['tasks']),
            'development_status':r['development_selection_status'][name]})
    bare={t['id']:t for t in final['evidence_aware']['tasks']};fallback={t['id']:t for t in final['evidence_with_fallback']['tasks']}
    preserved=[t['id'] for t in original['tasks'] if t['correct'] and not bare[t['id']]['correct'] and fallback[t['id']]['correct']]
    old_cfg=read_config('workspace/reliability-ci-proof/baseline');old_tasks={t['id']:t for t in load_benchmark(old_cfg)};old_chunks=scan_sources(old_cfg)[1]
    ci=json.loads(base.with_suffix('.data-ci.json').read_text())
    repaired=[]
    for repair in ci['repairs']:
        for task in repair['tasks']['tasks']:
            repaired.append({'task_id':task['id'],'correct':task['correct'],
                             'restored_reference_coverage':evidence_coverage(old_tasks[task['id']],task,old_chunks)})
    result={'measurement_kind':'genuine_local_generation','comparison':rows,
            'fresh_tasks':24,'development_tasks':12,'heldout_tasks':12,'heldout_groups':len({t['group_id'] for t in tasks.values() if t['split']=='heldout'}),
            'quality_rule':'No newly failed tasks; reference exact match unchanged. Semantic review pending.',
            'observed_fallback_preserved_tasks':preserved,
            'grouped_accuracy_delta_ci95_points':{name:grouped_accuracy_interval(original,variant,tasks) for name,variant in final.items()},
            'data_ci':{'controlled_cases':4,'fresh_heldout_evidence':False,'verdict':ci['verdict'],
                'normal_answer_failures':ci['simple_check_comparison']['answer_accuracy_new_failures'],
                'nonempty_retrieval_failures':ci['simple_check_comparison']['nonempty_retrieval_failures'],
                'reference_coverage_failures':ci['simple_check_comparison']['reference_coverage_failures'],
                'localization':[c for c in ci['task_changes'] if c['evidence_regression']],
                'controlled_repairs':repaired,'whole_source_ablation_new_failures':ci['ablation']['comparison']['lost_tasks'],
                'advantage_over_reference_coverage_detection':False,
                'added_context':'Frozen version localization and model-tested temporary repair; no competitor superiority or conclusive universal causal attribution.'},
            'session':json.loads(base.with_suffix('.session.json').read_text()),
            'groundedness':'pending independent claim review', 'production_changes_applied':False,
            'limitations':['12 held-out tasks and 9 groups cannot establish equivalence or general superiority.',
                'Potential conflict and sufficiency scores are uncalibrated heuristics.',
                'Historical snapshots do not constitute an independently adjudicated contradictory/outdated-source benchmark.',
                'Reference coverage is not semantic grounding and exact match can reject valid paraphrases.']}
    output=Path('docs/artifacts/reliability-summary.json');output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('Fallback preserved:',preserved)
    for row in rows:print(row['policy'],row['passed'],row['total_tokens'],row['complete_reference_tasks'],row['correct_without_context'])
    print('Repair:',repaired)

if __name__=='__main__':main()
