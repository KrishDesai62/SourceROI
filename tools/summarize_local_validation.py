"""Post-evaluation evidence diagnostics; never feeds held-out results into selection."""
import argparse
import json
import random
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import load_benchmark, scan_sources


def grouped_accuracy_interval(baseline, candidate, tasks, draws=2000):
    groups = {}
    for row in baseline['tasks']:
        task = tasks[row['id']]
        groups.setdefault(task['group_id'], []).append(task['id'])
    if len(groups) < 2:
        return None
    a = {r['id']: r['correct'] for r in baseline['tasks']}
    b = {r['id']: r['correct'] for r in candidate['tasks']}
    names = sorted(groups)
    generator = random.Random(1729)
    deltas = []
    for _ in range(draws):
        selected = [tid for _ in names for tid in groups[generator.choice(names)]]
        deltas.append(100*sum(int(b[tid])-int(a[tid]) for tid in selected)/len(selected))
    deltas.sort()
    return [round(deltas[int(.025*(draws-1))], 2), round(deltas[int(.975*(draws-1))], 2)]


def summarize(report, cfg):
    tasks = {t['id']: t for t in load_benchmark(cfg)}
    chunks = {c['id']: c for c in scan_sources(cfg)[1]}
    entries = {e['name']: e for e in report['experiments'] if e['partition'] == 'heldout'}
    development = [e for e in report['experiments'] if e['partition'] == 'development']
    original_dev = next(e for e in development if e['name'] == 'original')['runs'][0]
    original_correct = {r['id'] for r in original_dev['tasks'] if r['correct']}
    baseline_status = {}
    floor = report.get('quality_constraints', {}).get('accuracy_floor', 0)
    grounding_floor = report.get('quality_constraints', {}).get('groundedness_floor')
    for name in entries:
        if name == 'sourceroi':
            continue
        candidates = [e for e in development if e['name'] == name]
        eligible = []
        for entry in candidates:
            valid = all(v['metrics']['accuracy'] >= floor and
                        not any(r['id'] in original_correct and not r['correct'] for r in v['tasks']) and
                        (grounding_floor is None or all(r['groundedness'] is not None and r['groundedness'] >= grounding_floor for r in v['tasks']))
                        for v in entry['runs'])
            if valid:
                eligible.append(entry)
        baseline_status[name] = 'qualified' if eligible else 'no_qualifying_development_configuration'
    rows = []
    evidence = {}
    review_by_key = {item['key']: item for item in report['review_items']}
    heldout_reviews = {}
    for name, entry in entries.items():
        variant = entry['runs'][0]
        m = variant['metrics']
        diagnostics = []
        for row in variant['tasks']:
            key = row['grounding_review_key']
            if key in review_by_key:
                item = dict(review_by_key[key])
                item.update(task_id=row['id'], citations=row['citations'],
                            accepted_answers=tasks[row['id']]['accepted_answers'],
                            annotation_evidence=tasks[row['id']]['evidence'])
                if key not in heldout_reviews:
                    item['configurations'] = []
                    heldout_reviews[key] = item
                heldout_reviews[key]['configurations'].append(name)
            references = tasks[row['id']]['evidence']
            context = [chunks[cid] for cid in row['retrieved_chunk_ids']]
            found = [ref for ref in references if any(c['document_id'] == ref['document_id'] and ref['quote'] in c['text'] for c in context)]
            diagnostics.append({'task_id': row['id'], 'correct_exact_match': row['correct'],
                'actual': row['actual'], 'accepted_answers': tasks[row['id']]['accepted_answers'],
                'support_quote_coverage': len(found)/len(references) if references else None,
                'all_support_quotes_present': len(found) == len(references) if references else None})
        evidence[name] = diagnostics
        rows.append({'configuration': name, **{key: m.get(key) for key in
            ('task_count', 'passed', 'accuracy', 'input_tokens', 'output_tokens', 'total_tokens', 'context_tokens',
             'mean_latency_ms', 'median_latency_ms', 'p95_latency_ms', 'groundedness', 'total_cost_usd')},
            'full_reference_evidence_tasks': sum(d['all_support_quotes_present'] is True for d in diagnostics),
            'tasks_without_retrieved_context': sum(not r['retrieved_chunk_ids'] for r in variant['tasks']),
            'correct_without_retrieved_context': sum(r['correct'] and not r['retrieved_chunk_ids'] for r in variant['tasks']),
            'nonabstentions_without_retrieved_context': sum(not r['retrieved_chunk_ids'] and r['actual'] != 'INSUFFICIENT_EVIDENCE' for r in variant['tasks']),
            'quality_qualified_against_original': report['heldout_quality_qualified'][name],
            'development_selection_status': baseline_status.get(name, 'learned_candidate'),
            'newly_failed_against_original': report['comparisons'][name][0]['lost_tasks']})
    return {'kind': 'genuine_local_generation_summary', 'model': report['model'],
            'inference_settings': {k: cfg['model'].get(k) for k in
                ('name','base_url','runtime','local_only','context_tokenizer','compact_source_ids','response_format','seed','temperature','max_output_tokens','timeout_seconds')},
            'configuration_file_unchanged': cfg.get('_config_hash') == report.get('requested_config_hash'),
            'comparison': rows, 'development_baseline_status': baseline_status,
            'baseline_fallback_caveat': 'In the archived run, families with no feasible development setting used minimum-token failed settings. Those rows are unqualified diagnostics, not strong quality-preserving comparators. Future code prioritizes best observed development quality; this completed held-out run was not rerun.',
            'actual_external_api_spend_usd': 0, 'hardware_and_electricity_cost_usd': None,
            'groundedness_review_status': 'pending', 'heldout_review_items': list(heldout_reviews.values()), 'evidence_diagnostics': evidence,
            'recommendation': report['recommendation'],
            'grouped_accuracy_delta_ci95_points': {name: grouped_accuracy_interval(e['runs'][0], entries['sourceroi']['runs'][0], tasks)
                                                  for name, e in entries.items() if name != 'sourceroi'},
            'limitations': ['Reference quote coverage is not semantic grounding.',
                'Exact-match negatives can include valid paraphrases; independent review is pending.',
                'All held-out diagnostics are post-evaluation only; frozen policy hashes are retained in the raw report.',
                'This small local model and public dataset do not establish effects on commercial agent stacks.']}


def write(summary, output):
    output = Path(output)
    output.write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    lines = ['# Genuine local-model comparison', '',
             'External API spend: $0. Groundedness review: pending.', '',
             '| Policy | Correct | Prompt | Output | Total | Context tokens | Median ms | p95 ms | New failures |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in summary['comparison']:
        lines.append(f"| {row['configuration']} | {row['passed']}/{row['task_count']} | {row['input_tokens']} | {row['output_tokens']} | {row['total_tokens']} | {row['context_tokens']} | {row['median_latency_ms']} | {row['p95_latency_ms']} | {len(row['newly_failed_against_original'])} |")
    lines.extend(['', summary['recommendation']['deployment_verdict'], summary['recommendation']['reason'], '',
                  'Context/reference coverage and citation validity do not establish semantic groundedness.'])
    output.with_suffix('.review.json').write_text(json.dumps({'version': 1, 'items': summary['heldout_review_items']}, indent=2)+'\n')
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=Path('docs/artifacts/local-llm-96.json'))
    p.add_argument('--project', type=Path, default=Path('workspace/local-llm-96'))
    p.add_argument('--output', type=Path, default=Path('docs/artifacts/local-llm-96-summary.json'))
    args = p.parse_args()
    write(summarize(json.loads(args.input.read_text()), read_config(args.project)), args.output)
    print(args.output)
