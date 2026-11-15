"""Standalone, grouped evaluation of tuned baselines and development-fitted routing."""
from __future__ import annotations
from copy import deepcopy
import csv
import hashlib
import itertools
import json
import math
import logging
from pathlib import Path
import statistics
import time
from urllib.parse import urlparse

from . import db
from .engine import evaluate_variant, compare_variants, _objective_score
from .ingest import load_benchmark, scan_sources
from .policies import task_kind
from .validation import Budget, split_tasks
from .uncertainty import objective_interval


def policies(cfg):
    k = cfg.get('settings', {}).get('max_chunks', 6)
    chars = cfg.get('settings', {}).get('max_context_chars', 4000)
    choices = [('original', {'name': 'original'})]
    for small in range(1, k+1):
        choices.append(('top_k', {'name': 'top_k', 'k': small}))
    for size in sorted({128, 256, 512, max(1, chars//4), max(1, chars//2)}):
        choices.append(('context_budget', {'name': 'context_budget', 'chars': size}))
    for ratio in (.25, .5, .75, 1.0):
        choices.append(('threshold', {'name': 'threshold', 'ratio': ratio}))
    # Do not invent missing fees to make a cost baseline look measured.
    if all(s.get('per_call_price_usd') is not None for s in cfg['sources']):
        for count in range(1, k+1):
            choices.append(('cheapest', {'name': 'cheapest', 'k': count}))
    for count in range(1, k+1):
        choices.append(('task_aware', {'name': 'task_aware', 'k': count}))
    for count in sorted({1, max(1, k//2), k}):
        for weight in ((0, .5) if all(s.get('per_call_price_usd') is not None for s in cfg['sources']) else (0,)):
            choices.append(('coverage', {'name': 'coverage', 'k': count, 'cost_weight': weight}))
    source_ids = sorted(s['id'] for s in cfg['sources'])
    limit = cfg.get('settings', {}).get('study_source_candidates', 8)
    exclusions = itertools.islice((list(c) for n in range(1, len(source_ids))
                                   for c in itertools.combinations(source_ids, n)), limit)
    for excluded in exclusions:
        choices.append(('coverage', {'name': 'coverage', 'k': k, 'cost_weight': 0,
                                     'excluded_sources': excluded}))
    return choices


def subset_metrics(variant, ids):
    rows = [t for t in variant['tasks'] if t['id'] in ids]
    if not rows:
        raise ValueError('Cannot score an empty task group')
    def known_sum(field):
        return sum(t[field] for t in rows) if all(t[field] is not None for t in rows) else None
    model, data = known_sum('model_cost_usd'), known_sum('data_cost_usd')
    input_tokens, output_tokens = known_sum('prompt_tokens'), known_sum('completion_tokens')
    return {'accuracy': sum(t['correct'] for t in rows)/len(rows),
            'passed': sum(t['correct'] for t in rows),
            'total_cost_usd': model+data if model is not None and data is not None else None,
            'mean_latency_ms': statistics.mean(t['end_to_end_latency_ms'] for t in rows),
            'p95_latency_ms': sorted(t['end_to_end_latency_ms'] for t in rows)[math.ceil(.95*len(rows))-1],
            'total_tokens': input_tokens+output_tokens if input_tokens is not None and output_tokens is not None else None}


def run_study(cfg, *, objective='token_budget', quality_floor=.95, repeats=1,
              min_groundedness=.9, reviews=None, approved_spend_usd=None, notify=None):
    if cfg.get('runner', 'rag_chat') != 'rag_chat':
        raise ValueError('Study retrieval policies require the built-in RAG runner; external capabilities are unsupported')
    for value in (quality_floor,):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Quality floor must be finite in [0,1]')
    if min_groundedness is not None and (type(min_groundedness) not in (int, float) or not math.isfinite(min_groundedness) or not 0 <= min_groundedness <= 1):
        raise ValueError('Groundedness floor must be finite in [0,1] or null')
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError('repeats must be 1..10')
    _objective_score({}, objective)
    remote = urlparse(cfg.get('model', {}).get('base_url', '')).hostname not in ('localhost', '127.0.0.1', '::1')
    if approved_spend_usd is not None and (type(approved_spend_usd) not in (int, float) or not math.isfinite(approved_spend_usd) or approved_spend_usd <= 0):
        raise ValueError('Approved spend must be a positive finite number')
    if remote and approved_spend_usd is None:
        raise ValueError('Remote model execution requires an explicitly approved spend; no requests sent')
    cfg = deepcopy(cfg)
    cfg.setdefault('settings', {})
    if remote:
        model = cfg.get('model', {})
        if any(model.get(k) is None for k in ('input_price_per_million_usd', 'output_price_per_million_usd')):
            raise ValueError('Explicit model pricing is required before a paid study')
        current = cfg['settings'].get('max_estimated_model_cost_usd')
        cfg['settings']['max_estimated_model_cost_usd'] = min(current, approved_spend_usd) if current is not None else approved_spend_usd
    tasks = load_benchmark(cfg)
    dev, heldout = split_tasks(tasks)
    if not heldout:
        raise ValueError('Study requires nonempty grouped development and held-out partitions')
    task_limit = cfg['settings'].get('max_tasks_per_run', 50)
    if max(len(dev), len(heldout)) > task_limit:
        raise ValueError('Study exceeds max_tasks_per_run; use a smaller independently frozen benchmark')
    docs, chunks = scan_sources(cfg)
    provenance = None
    if cfg.get('data_provenance'):
        from .config import secure_path
        provenance = secure_path(Path(cfg['_root']), cfg['data_provenance'])
        if json.loads(provenance.read_text()).get('kind') == 'published_external_data':
            from .datasets import verify_public_snapshot
            verify_public_snapshot(cfg, docs)
    if not docs:
        raise ValueError('Study requires source documents')
    choices = policies(cfg)
    families = sorted({name for name, _ in choices} - {'coverage'})
    # Baseline families tune their hyperparameters on development only.
    required = repeats*len(choices)*len(dev)+(len(families)+1)*len(heldout)
    budget = Budget(cfg['settings'])
    if required > budget.limit:
        raise ValueError(f'Study needs at most {required} model calls, above cap {budget.limit}')
    report = {'version': 2, 'kind': 'standalone_policy_study', 'objective': objective,
              'measurement_kind': cfg.get('measurement_kind', 'unverified_endpoint'),
              'requested_config_hash': cfg.get('_config_hash'),
              'config_hash': hashlib.sha256(json.dumps({k: v for k, v in cfg.items() if not k.startswith('_')},
                                        sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
              'model': {k: cfg['model'].get(k) for k in ('name', 'base_url', 'temperature', 'max_output_tokens', 'runtime', 'local_only', 'context_tokenizer', 'seed',
                       'input_price_per_million_usd', 'output_price_per_million_usd')},
              'code_sha256': {name: hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                              for name in ('study.py', 'engine.py', 'provider.py', 'policies.py', 'grade.py', 'ingest.py')},
              'quality_constraints': {'accuracy_floor': quality_floor, 'no_new_task_losses': True, 'groundedness_floor': min_groundedness},
              'execution_plan': {'development_repeats': repeats, 'heldout_repeats': 1, 'max_calls': required},
              'corpus_sha256': {d['id']: d['fingerprint'] for d in docs},
              'benchmark_sha256': hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest(),
              'partitions': {name: [t['id'] for t in part] for name, part in [('development', dev), ('heldout', heldout)]},
              'review_status': 'declared_independent' if all(t.get('review_status') == 'independent' and t.get('reviewer') for t in tasks) else 'unreviewed_or_incomplete',
              'data_provenance_sha256': hashlib.sha256(provenance.read_bytes()).hexdigest() if provenance else None,
              'data_provenance': json.loads(provenance.read_text()) if provenance else None,
              'status': 'running', 'deployment': 'requires_further_testing',
              'experiments': [], 'invalid_experiments': [], 'review_items': [],
              'limitations': ['Human review provenance is declared, not independently authenticated.',
                             'Claim support is scored only from completed reviewer adjudications.',
                             'Context character budgets and retrieval utilities are selection estimates, not observed tokens.',
                             'Post-call cost guards can overshoot on an in-flight call; use a provider hard cap.',
                             'This study never deploys retrieval changes.']}
    if tasks and all(t.get('review_status') == 'published_dataset_annotations' for t in tasks):
        report['review_status'] = 'published_dataset_annotations'
    if 'cheapest' not in families:
        report['invalid_experiments'].append({'name': 'cheapest', 'reason': 'Explicit source prices are missing'})
    rid = db.begin(cfg, 'policy_study', [])
    start = time.perf_counter()
    pending = []
    def publish(event, **fields):
        progress = {'event': event, 'run_id': rid, 'calls': budget.calls, 'max_calls': required, **fields}
        report['progress'] = progress
        logging.getLogger('sourceroi.experiments').info('experiment_progress', extra={'experiment': progress})
        if notify:
            notify(progress)
    def execute(name, partition, selected, policy):
        local = deepcopy(cfg)
        local['settings']['retrieval_policy'] = policy
        local['_experiment_budget'], local['_grounding_reviews'] = budget, reviews or {}
        local['_review_items'] = pending
        entry = {'name': name, 'partition': partition, 'policy': policy, 'runs': []}
        report['experiments'].append(entry)
        for repetition in range(repeats if partition == 'development' else 1):
            local['_partial_tasks'] = []
            local['_active_request'] = {}
            entry['incomplete_tasks'] = local['_partial_tasks']
            entry['active_request'] = local['_active_request']
            publish('configuration_started', configuration=name, partition=partition, repeat=repetition)
            variant = evaluate_variant(local, selected, chunks, [])
            variant['repeat'] = repetition
            entry['runs'].append(variant)
            entry.pop('incomplete_tasks', None)
            entry.pop('active_request', None)
            publish('configuration_completed', configuration=name, partition=partition, repeat=repetition)
            db.checkpoint(cfg, rid, report)
        return entry
    def score(entry, ids):
        return statistics.mean(_objective_score(subset_metrics(v, ids), objective) for v in entry['runs'])
    def admissible(entry, reference, ids):
        for variant, base in zip(entry['runs'], reference['runs']):
            selected = [r for r in variant['tasks'] if r['id'] in ids]
            original = {r['id']: r for r in base['tasks']}
            if not selected or sum(r['correct'] for r in selected)/len(selected) < quality_floor:
                return False
            if any(original[r['id']]['correct'] and not r['correct'] for r in selected):
                return False
            if min_groundedness is not None and any(r['groundedness'] is None or r['groundedness'] < min_groundedness for r in selected):
                return False
        return True
    try:
        evaluated = [execute(name, 'development', dev, policy) for name, policy in choices]
        baseline = evaluated[0]
        fitting_started = time.perf_counter()
        ids = {t['id'] for t in dev}
        frozen = {}
        report['development_selection_status'] = {}
        for family in families:
            family_entries = [e for e in evaluated if e['name'] == family]
            eligible = [e for e in family_entries if admissible(e, baseline, ids)]
            if eligible:
                chosen_baseline = min(eligible, key=lambda e: (score(e, ids), json.dumps(e['policy'], sort_keys=True)))
                report['development_selection_status'][family] = 'qualified'
            else:
                # An infeasible family must not be made artificially weak by selecting
                # its cheapest failed setting. Preserve its best observed quality and
                # clearly mark it unqualified; no held-out outcome enters this choice.
                def fallback_rank(entry):
                    accuracy = min(subset_metrics(v, ids)['accuracy'] for v in entry['runs'])
                    losses = sum(len(compare_variants(a, b)['lost_tasks']) for a, b in zip(baseline['runs'], entry['runs']))
                    return (-accuracy, losses, score(entry, ids), json.dumps(entry['policy'], sort_keys=True))
                chosen_baseline = min(family_entries, key=fallback_rank)
                report['development_selection_status'][family] = 'no_qualifying_development_configuration'
            frozen[family] = chosen_baseline['policy']
        mapping = {}
        for kind in sorted({task_kind(t['question']) for t in dev}):
            group = {t['id'] for t in dev if task_kind(t['question']) == kind}
            eligible = [e for e in evaluated if admissible(e, baseline, group) and math.isfinite(score(e, group))]
            mapping[kind] = min(eligible, key=lambda e: (score(e, group), json.dumps(e['policy'], sort_keys=True)))['policy'] if eligible else {'name': 'original'}
        learned = {'name': 'learned', 'by_kind': mapping}
        # Freeze every baseline and learned decision before any held-out call.
        report['policy_fit_elapsed_ms'] = round((time.perf_counter()-fitting_started)*1000, 2)
        report['frozen_policies'] = {**frozen, 'sourceroi': learned}
        report['frozen_policy_sha256'] = hashlib.sha256(json.dumps(report['frozen_policies'], sort_keys=True).encode()).hexdigest()
        final = {name: execute(name, 'heldout', heldout, policy) for name, policy in report['frozen_policies'].items()}
        hid = {t['id'] for t in heldout}
        hb, hc = final['original'], final['sourceroi']
        report['category_changes'] = []
        for before, after in zip(hb['runs'], hc['runs']):
            original_rows = {r['id']: r for r in before['tasks']}
            summary = {}
            for row in after['tasks']:
                category = row['category']
                summary[category] = summary.get(category, 0) + int(row['correct']) - int(original_rows[row['id']]['correct'])
            report['category_changes'].append(summary)
        report['comparisons'] = {name: [compare_variants(a, b) for a, b in zip(hb['runs'], e['runs'])] for name, e in final.items()}
        report['heldout_quality_qualified'] = {name: admissible(e, hb, hid) for name, e in final.items()}
        observed_models = {r['model'] for e in report['experiments'] for v in e['runs'] for r in v['tasks']}
        report['observed_models'] = sorted(observed_models)
        report['execution_comparable'] = len(observed_models) == 1
        if not report['execution_comparable']:
            report['invalid_experiments'].append({'reason': 'Model identity changed during the study; source-only attribution is invalid'})
            report['heldout_quality_qualified'] = {name: False for name in report['heldout_quality_qualified']}
        safe = report['heldout_quality_qualified']['sourceroi']
        candidate_score = score(hc, hid)
        competitors = {name: e for name, e in final.items() if name != 'sourceroi' and report['heldout_quality_qualified'][name]}
        report['heldout_objective_scores'] = {name: (score(e, hid) if math.isfinite(score(e, hid)) else None) for name, e in final.items()}
        report['objective_delta_ci95'] = {name: objective_interval(e, hc, heldout, objective)
                                          for name, e in final.items() if name != 'sourceroi'}
        report['objective_uncertainty_note'] = 'Group bootstrap on held-out issuer/filing groups; repeated runs are averaged within tasks, not independent observations. Negative deltas favor SourceROI. Small group counts limit inference.'
        report['external_advantage_verified'] = False
        report['simple_baseline_comparisons'] = {}
        report['benefits_over_simple_baselines'] = {}
        for name, entry in final.items():
            if name in ('original', 'sourceroi'):
                continue
            comparisons = [compare_variants(a, b) for a, b in zip(entry['runs'], hc['runs'])]
            report['simple_baseline_comparisons'][name] = comparisons
            no_new_losses = all(not comparison['lost_tasks'] for comparison in comparisons)
            report['benefits_over_simple_baselines'][name] = (safe and report['heldout_quality_qualified'][name]
                and no_new_losses and math.isfinite(candidate_score) and candidate_score < score(entry, hid))
        report['outperforms_all_qualified_baselines_observed'] = (safe and bool(competitors)
            and math.isfinite(candidate_score) and all(candidate_score < score(e, hid) for e in competitors.values())
            and all(report['benefits_over_simple_baselines'].get(name, True) for name in competitors))
        incomplete_grounding = min_groundedness is not None and any(
            r['groundedness'] is None for v in hc['runs'] for r in v['tasks'])
        measured_quality_failure = any(v['metrics']['accuracy'] < quality_floor for v in hc['runs']) or any(
            c['lost_tasks'] for c in report['comparisons']['sourceroi']) or (
                min_groundedness is not None and any(r['groundedness'] is not None and r['groundedness'] < min_groundedness
                                                     for v in hc['runs'] for r in v['tasks']))
        report['observed_verdict'] = ('inconclusive_model_changed' if not report['execution_comparable'] else
            'quality_rejected' if measured_quality_failure else
            'inconclusive_unreviewed_grounding' if incomplete_grounding else
            'lower_observed_objective' if report['outperforms_all_qualified_baselines_observed'] else 'no_demonstrated_advantage')
        # Held-out losses are rejected regardless of missing grounding reviews.
        lost = {tid for c in report['comparisons']['sourceroi'] for tid in c['lost_tasks']}
        report['deployment'] = ('inconclusive' if not report['execution_comparable'] else
                                'rejected' if measured_quality_failure else 'requires_further_testing')
        tradeoffs = []
        for name, entry in final.items():
            metrics = entry['runs'][0]['metrics']
            tradeoffs.append({'name': name, **{key: metrics[key] for key in
                ('accuracy', 'total_tokens', 'total_cost_usd', 'mean_latency_ms', 'p95_latency_ms')}})
        def dominates(a, b):
            keys = ('total_tokens', 'total_cost_usd', 'p95_latency_ms')
            if any(a[k] is None or b[k] is None for k in keys):
                return False
            return a['accuracy'] >= b['accuracy'] and all(a[k] <= b[k] for k in keys) and (a['accuracy'] > b['accuracy'] or any(a[k] < b[k] for k in keys))
        report['observed_pareto_frontier'] = [t for t in tradeoffs if not any(dominates(o, t) for o in tradeoffs)]
        report['pareto_note'] = 'First held-out repetition; descriptive only. Unknown metrics cannot establish dominance.'
        report['status'] = 'completed'
        report['api_calls'] = budget.calls
        report['elapsed_ms'] = round((time.perf_counter()-start)*1000, 2)
        report['evaluation_task_wall_ms'] = round(sum(t['end_to_end_latency_ms'] for e in report['experiments']
            for v in e['runs'] for t in v['tasks']), 2)
        report['overhead_elapsed_ms'] = round(max(0, report['elapsed_ms']-report['evaluation_task_wall_ms']), 2)
        report['evaluation_model_cost_usd'] = budget.cost if budget.cost_known else None
        report['review_items'] = list({item['key']: item for item in pending}.values())
        report['run_id'] = rid
        from .recommendation import build_recommendation
        report['recommendation'] = build_recommendation(report, cfg, heldout)
        publish('completed')
        db.finish(cfg, rid, report)
        return report
    except Exception as exc:
        report.update(status='incomplete', deployment='inconclusive', api_calls=budget.calls)
        report['review_items'] = list({item['key']: item for item in pending}.values())
        if report['experiments'] and report['experiments'][-1].get('active_request'):
            report['experiments'][-1]['active_request'].update(status='unvalidated', error_type=type(exc).__name__)
        report['invalid_experiments'].append({'error_type': type(exc).__name__})
        publish('failed', error_type=type(exc).__name__)
        db.finish(cfg, rid, report, 'Study incomplete: '+type(exc).__name__)
        raise


def export_study(report, path):
    """JSON, CSV, Markdown, and an unresolved human-review packet."""
    path = Path(path)
    if report.get('status') != 'completed':
        raise ValueError('Only completed studies can be exported as final comparisons')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    rows = []
    for e in report['experiments']:
        for v in e['runs']:
            rows.append({'configuration': e['name'], 'partition': e['partition'], 'repeat': v['repeat'], **v['metrics']})
    with path.with_suffix('.csv').open('w', newline='') as output:
        fields = list(dict.fromkeys(k for row in rows for k in row))
        writer = csv.DictWriter(output, fields)
        writer.writeheader()
        writer.writerows(rows)
    lines = ['# Standalone SourceROI study', '', 'Evidence: '+report['measurement_kind'],
             'Review status: '+report['review_status'], 'Verdict: '+report['observed_verdict'],
             'Deployment: '+report.get('recommendation', {}).get('deployment_verdict', report['deployment']), '',
             '| Configuration | Repeat | Accuracy | Tokens | Cost USD | Groundedness |', '|---|---:|---:|---:|---:|---:|']
    for row in rows:
        if row['partition'] == 'heldout':
            lines.append(f"| {row['configuration']} | {row['repeat']} | {row['accuracy']} | {row['total_tokens']} | {row['total_cost_usd']} | {row['groundedness']} |")
    if report.get('recommendation'):
        recommendation = report['recommendation']
        lines.extend(['', '## Offline recommendation', '', recommendation['reason'], '',
                      '```json', json.dumps(recommendation['per_task_kind'], indent=2), '```', '',
                      'Attribution: '+recommendation['attribution_note']])
    lines.extend(['', 'These are observed comparisons, not proof of statistical superiority. See JSON for paired uncertainty and task evidence.'])
    path.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    path.with_suffix('.review.json').write_text(json.dumps({'version': 1, 'items': report['review_items']}, indent=2)+'\n')
