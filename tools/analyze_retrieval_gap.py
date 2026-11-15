"""Explain the already exposed eight-task retrieval comparison, without new tuning."""
import argparse
import json
from pathlib import Path


def analyze(report):
    comparisons = report['comparisons']
    threshold, proxy = comparisons['threshold'], comparisons['sourceroi_retrieval_proxy']
    base = {t['id']: t for t in threshold['tasks']}
    changes = []
    for task in proxy['tasks']:
        reference = base[task['id']]
        changes.append({'task_id': task['id'],
                        'threshold_chars': reference['context_characters'], 'proxy_chars': task['context_characters'],
                        'extra_proxy_chars': task['context_characters']-reference['context_characters'],
                        'threshold_quote_coverage': reference['support_quote_coverage'],
                        'proxy_quote_coverage': task['support_quote_coverage'],
                        'threshold_chunks': len(reference['selected_chunks']), 'proxy_chunks': len(task['selected_chunks'])})
    return {'kind': 'previous_exposed_benchmark_root_cause',
        'threshold_policy': threshold['frozen_policy'], 'proxy_policy': proxy['frozen_policy'], 'tasks': changes,
        'extra_proxy_context_chars': proxy['context_characters']-threshold['context_characters'],
        'findings': [
            'The threshold policy drops chunks below half the top BM25 score; it keeps only one chunk on each exposed SQuAD task.',
            'The fitted proxy routes lookup questions to coverage selection with Hotpot excluded, and multi-evidence questions to a 2000-character context budget.',
            'Coverage selection can retain passages after all query terms are covered because normalized BM25 relevance remains positive; it stops at k or negative utility, not at zero novel query coverage.',
            'Exact normalized duplicate removal does not remove semantically overlapping or near-duplicate passages.',
            'Question types are a three-way keyword rule, and only four development questions fitted the exposed proxy; dataset-specific source exclusion can overfit those types.',
            'This is task-aware routing among static policies with source exclusion, not learned semantic information value or authority/recency reasoning.',
            'Equal reference quote coverage does not establish equal generated-answer quality, and context characters are not observed model tokens.'
        ],
        'policy_change_applied': False,
        'next_test': 'Freeze a larger document-grouped benchmark and evaluate genuinely local generation before adopting an optimizer change.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = analyze(json.loads(args.input.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'extra_proxy_context_chars': result['extra_proxy_context_chars']}))
