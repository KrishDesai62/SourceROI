"""Actionable offline proposals with explicit uncertainty and evidence limits."""
from collections import Counter

RECOMMENDED = 'Recommended for further deployment testing'
REJECTED = 'Rejected due to quality regression'
INCONCLUSIVE = 'Inconclusive / insufficient evidence'


def build_recommendation(report, cfg, heldout):
    entries = {e['name']: e for e in report['experiments'] if e['partition'] == 'heldout'}
    baseline, candidate = entries['original']['runs'][0], entries['sourceroi']['runs'][0]
    bm, cm = baseline['metrics'], candidate['metrics']
    delta = lambda key: cm[key]-bm[key] if cm.get(key) is not None and bm.get(key) is not None else None
    all_sources = sorted(s['id'] for s in cfg['sources'])
    policy = report['frozen_policies']['sourceroi']
    by_kind = {}
    for kind, selection in policy.get('by_kind', {}).items():
        excluded = selection.get('excluded_sources', [])
        by_kind[kind] = {'included_datasets': [sid for sid in all_sources if sid not in excluded],
                         'excluded_datasets': excluded, 'retrieval_settings': selection}
    before = {t['id']: t for t in baseline['tasks']}
    changes = []
    for task in candidate['tasks']:
        a, b = set(before[task['id']]['retrieved_chunk_ids']), set(task['retrieved_chunk_ids'])
        changes.append({'task_id': task['id'], 'removed_passages': sorted(a-b), 'added_passages': sorted(b-a),
                        'before_correct': before[task['id']]['correct'], 'after_correct': task['correct']})
    usage = Counter(cid.split('#chunk', 1)[0] for t in candidate['tasks'] for cid in t['retrieved_chunk_ids'])
    groups = {t.get('group_id', t['id']) for t in heldout}
    review_complete = report['review_status'] in ('declared_independent', 'published_dataset_annotations') and cm.get('groundedness') is not None
    qualified = report['heldout_quality_qualified']['sourceroi']
    real = report['measurement_kind'] in ('external_provider', 'local_generation') and all(t['usage_source'] == 'provider_reported' for t in candidate['tasks'])
    scores = report['heldout_objective_scores']
    improves = scores.get('sourceroi') is not None and scores.get('original') is not None and scores['sourceroi'] < scores['original']
    baseline_benefit = any(report.get('benefits_over_simple_baselines', {}).values())
    if not report.get('execution_comparable', True):
        verdict = INCONCLUSIVE
        reason = 'Model identity changed during the study; information-policy comparisons are invalid.'
    elif report['deployment'] == 'rejected':
        verdict = REJECTED
        reason = 'Held-out quality failed a configured threshold or introduced a newly incorrect task.'
    elif real and qualified and review_complete and improves and baseline_benefit and len(groups) >= 10:
        verdict = RECOMMENDED
        reason = 'Observed held-out efficiency improvement passed configured quality constraints; validate deployment separately.'
    else:
        verdict = INCONCLUSIVE
        reason = 'Real-model provenance, independent annotations, groundedness review, efficiency improvement, or sufficient held-out groups are missing.'
    comparisons = report['comparisons']['sourceroi'][0]
    return {'deployment_verdict': verdict, 'reason': reason,
            'baseline_configuration': report['frozen_policies']['original'],
            'candidate_configuration': policy, 'per_task_kind': by_kind,
            'delta_input_tokens': delta('input_tokens'), 'delta_output_tokens': delta('output_tokens'),
            'delta_total_tokens': delta('total_tokens'), 'delta_accuracy': delta('accuracy'),
            'delta_groundedness': delta('groundedness'), 'delta_mean_latency_ms': delta('mean_latency_ms'),
            'delta_median_latency_ms': delta('median_latency_ms'), 'delta_p95_latency_ms': delta('p95_latency_ms'),
            'delta_total_cost_usd': delta('total_cost_usd'),
            'cost_per_task_usd': cm['cost_per_task_usd'], 'cost_per_success_usd': cm['cost_per_success_usd'],
            'lost_tasks': comparisons['lost_tasks'], 'improved_tasks': comparisons['gained_tasks'],
            'paired_accuracy_delta_ci95_points': comparisons['paired_delta_ci95_points'],
            'objective_delta_ci95': report['objective_delta_ci95'].get('original'),
            'heldout_groups': len(groups), 'benefits_over_simple_baselines': report.get('benefits_over_simple_baselines', {}), 'passage_changes': changes,
            'document_exposure_counts': dict(sorted(usage.items())),
            'attribution_note': 'Exposure and passage changes are observations, not causal contribution. Use controlled source/document ablations for contribution estimates.',
            'risks': ['No detected loss does not prove equivalence or safety on unseen workloads.',
                      'Public benchmark labels may be imperfect and questions may occur in model pretraining.',
                      'Grounding review provenance and declared real-provider provenance require independent verification.'],
            'automatically_applied': False}
