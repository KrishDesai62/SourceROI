"""Bounded development search and sealed held-out validation; never deploys changes."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import time

from .ingest import load_benchmark, scan_sources


class Budget:
    def __init__(self, settings):
        self.limit = settings.get('max_model_calls_per_run', 100)
        self.ceiling = settings.get('max_estimated_model_cost_usd')
        self.calls = 0
        self.cost = 0.0
        self.cost_known = True
        self.started = time.monotonic()
        self.max_seconds = settings.get('max_run_seconds')

    def remaining_seconds(self):
        return max(.001, self.max_seconds-(time.monotonic()-self.started)) if self.max_seconds is not None else None

    def check_time(self):
        if self.max_seconds is not None and time.monotonic()-self.started >= self.max_seconds:
            raise ValueError('Experiment duration cap reached')

    def before(self):
        self.check_time()
        if getattr(self,'resource_check',None):
            self.resource_check()
        if self.calls >= self.limit:
            raise ValueError('Experiment model-call cap reached')
        if self.ceiling is not None and self.cost >= self.ceiling:
            raise ValueError('Experiment estimated cost ceiling reached')
        self.calls += 1

    def after(self, result):
        cost = result['model_cost_usd']
        if cost is None:
            self.cost_known = False
        if self.ceiling is not None and cost is None:
            raise ValueError('Cannot enforce cost ceiling without reported usage and pricing')
        self.cost += cost or 0.0
        if self.ceiling is not None and self.cost > self.ceiling:
            raise ValueError('Estimated cost ceiling exceeded; final in-flight call can overshoot')


def split_tasks(tasks):
    """Explicit partitions preferred; otherwise stable task-ID hash, independent of answers."""
    explicit = any(t.get('split') for t in tasks)
    if explicit:
        if any(t.get('split') not in ('development', 'heldout') for t in tasks):
            raise ValueError('Every task needs a split when explicit partitions are used')
        dev = [t for t in tasks if t['split'] == 'development']
        heldout = [t for t in tasks if t['split'] == 'heldout']
    elif len(tasks) >= 4:
        groups = sorted({t.get('group_id', t['id']) for t in tasks},
                        key=lambda value: hashlib.sha256(value.encode()).hexdigest())
        chosen_groups = set(groups[:max(1, len(groups)//4)])
        heldout = sorted([t for t in tasks if t.get('group_id', t['id']) in chosen_groups], key=lambda t: t['id'])
        dev = sorted([t for t in tasks if t.get('group_id', t['id']) not in chosen_groups], key=lambda t: t['id'])
    else:
        dev, heldout = tasks, []
    groups_dev = {t.get('group_id', t['id']) for t in dev}
    groups_heldout = {t.get('group_id', t['id']) for t in heldout}
    if groups_dev & groups_heldout:
        raise ValueError('Task groups overlap development and held-out partitions')
    if not dev:
        raise ValueError('Development partition must not be empty')
    return dev, heldout


def optimize(cfg, *, quality_floor=.9, min_citation_rate=.75, objective='cost_per_success',
             max_tasks=None, max_candidates=8, repeats=1, max_accuracy_drop=0.0,
             max_regressions=0):
    from .engine import evaluate_variant, compare_variants, _objective_score, _percent_change
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in
           (quality_floor, min_citation_rate, max_accuracy_drop)):
        raise ValueError('Quality thresholds must be finite values between zero and one')
    if type(max_candidates) is not int or not 1 <= max_candidates <= 64:
        raise ValueError('max_candidates must be 1..64')
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError('repeats must be 1..10')
    if type(max_regressions) is not int or max_regressions < 0:
        raise ValueError('max_regressions must be nonnegative')
    if max_tasks is not None and (type(max_tasks) is not int or max_tasks < 1):
        raise ValueError('max_tasks must be positive')
    _objective_score({}, objective)  # Validate before any calls.
    tasks = load_benchmark(cfg)
    dev, heldout = split_tasks(tasks)
    limit = min(max_tasks or 200, cfg.get('settings', {}).get('max_tasks_per_run', 50))
    dev, heldout = dev[:limit], heldout[:limit]
    docs, chunks = scan_sources(cfg)
    if not docs or not dev:
        raise ValueError('Optimization requires documents and development tasks')
    sources = sorted(s['id'] for s in cfg['sources'])
    # Deterministic subset enumeration captures interactions among evaluated subsets.
    subsets = list(itertools.islice((list(c) for n in range(1, len(sources)+1)
                                   for c in itertools.combinations(sources, n)), max_candidates))
    external = cfg.get('runner', 'rag_chat') != 'rag_chat'
    required = (1 + len(subsets) + (0 if external else 1) + bool(sources))*len(dev)*repeats + 4*len(heldout)*repeats
    budget = Budget(cfg.get('settings', {}))
    if required > budget.limit:
        raise ValueError(f'Validation needs at most {required} model calls, above cap {budget.limit}')
    report = {'version': 3, 'created_at': datetime.now(timezone.utc).isoformat(),
              'status': 'running', 'objective': objective, 'quality_floor': quality_floor,
              'measurement_kind': cfg.get('measurement_kind', 'unverified_endpoint'),
              'config_hash': cfg.get('_config_hash'),
              'runner': cfg.get('runner', 'rag_chat'),
              'model': {k: cfg.get('model', {}).get(k) for k in
                        ('name', 'temperature', 'max_output_tokens', 'input_price_per_million_usd',
                         'output_price_per_million_usd')},
              'quality_constraints': {'accuracy_floor': quality_floor, 'citation_rate_floor': min_citation_rate,
                                      'max_accuracy_drop': max_accuracy_drop, 'max_regressions': max_regressions},
              'benchmark_sha256': hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest(),
              'manifest': {d['id']: d['fingerprint'] for d in docs},
              'split': {'development_ids': [t['id'] for t in dev], 'heldout_ids': [t['id'] for t in heldout]},
              'repeats': repeats, 'experiments': [], 'invalid_experiments': [],
              'deployment': 'inconclusive',
              'limitations': ['Citation validity is not groundedness; semantic groundedness and unsupported claims are unmeasured.',
                             'No detected regression is not proof of equivalence. Bootstrap intervals can collapse on small samples.',
                             'USD values are configured-price estimates or agent reports, not verified invoices.',
                             'Cost ceiling is checked after each call; an in-flight call can overshoot.',
                             'No live retrieval configuration is changed.']}
    def evaluate(name, partition, selected, excluded, configuration):
        local = deepcopy(configuration)
        local['_experiment_budget'] = budget
        runs = []
        for repeat in range(repeats):
            v = evaluate_variant(local, selected, chunks, excluded, [])
            v['repeat'] = repeat
            runs.append(v)
        entry = {'name': name, 'partition': partition, 'excluded_sources': excluded,
                 'retrieval': configuration.get('settings', {}), 'runs': runs}
        report['experiments'].append(entry)
        return runs

    def acceptable(base, candidate):
        m = candidate['metrics']
        return (m['accuracy'] >= quality_floor and
                m['accuracy'] >= base['metrics']['accuracy'] - max_accuracy_drop and
                m['citation_format_rate'] >= min_citation_rate and
                len(compare_variants(base, candidate)['lost_tasks']) <= max_regressions)

    def score(runs):
        return sum(_objective_score(v['metrics'], objective) for v in runs)/len(runs)

    try:
        baseline = evaluate('original', 'development', dev, [], cfg)
        candidates = []
        for excluded in subsets:
            runs = evaluate('source_subset', 'development', dev, excluded, cfg)
            if all(acceptable(a, b) for a, b in zip(baseline, runs)) and math.isfinite(score(runs)):
                candidates.append((score(runs), excluded, runs))
        reduced = deepcopy(cfg)
        reduced['settings']['max_chunks'] = max(1, cfg.get('settings', {}).get('max_chunks', 6)//2)
        if external:
            report['invalid_experiments'].append({'name': 'top_k', 'reason': 'External adapter has no top-k capability'})
        else:
            evaluate('top_k', 'development', dev, [], reduced)
        fees = {s['id']: s.get('per_call_price_usd') or 0 for s in cfg['sources']}
        heuristic = [max(sources, key=lambda sid: (fees[sid], sid))] if sources else []
        evaluate('fixed_source_drop', 'development', dev, heuristic, cfg)
        best = min(candidates, key=lambda c: (c[0], c[1])) if candidates else None
        excluded = best[1] if best and best[0] < score(baseline) else []
        chosen = best[2] if excluded else baseline
        report['experiments'].append({'name': 'sourceroi', 'partition': 'development',
                                      'excluded_sources': excluded, 'runs': chosen})
        report['baseline'] = baseline[0]['metrics']
        report['status'] = 'ok' if excluded else 'no_valid_reduction'
        comparison = compare_variants(baseline[0], chosen[0])
        report['comparison'] = comparison
        bm, cm = baseline[0]['metrics'], chosen[0]['metrics']
        report['recommended'] = {'excluded_sources': excluded, 'decision': 'candidate' if excluded else 'keep',
            'accuracy': cm['accuracy'], 'citation_format_rate': cm['citation_format_rate'],
            'groundedness': None, 'delta_accuracy_points': comparison['delta_accuracy_points'],
            'delta_cost_usd': comparison['delta_cost_usd'],
            'input_token_reduction_pct': _percent_change(bm['provider_reported_prompt_tokens'], cm['provider_reported_prompt_tokens']),
            'total_token_reduction_pct': _percent_change(bm['total_tokens'], cm['total_tokens']),
            'task_regressions': comparison['lost_tasks'], 'task_improvements': comparison['gained_tasks'],
            'reason': 'Best measured qualifying development subset; deployment requires held-out validation.'}
        report['candidates'] = [{'score': c[0], 'excluded_sources': c[1]} for c in candidates]
        if heldout:
            # Selection is frozen above. Held-out outcomes never feed back into search.
            hb = evaluate('original', 'heldout', heldout, [], cfg)
            hc = evaluate('sourceroi', 'heldout', heldout, excluded, cfg)
            hh = evaluate('fixed_source_drop', 'heldout', heldout, heuristic, cfg)
            ht = evaluate('top_k', 'heldout', heldout, [], reduced) if not external else []
            report['heldout_comparisons'] = [compare_variants(a, b) for a, b in zip(hb, hc)]
            safe = all(acceptable(a, b) for a, b in zip(hb, hc))
            better = score(hc) < score(hb) and any(score(hc) < score(h) for h in (hh, ht) if h)
            report['deployment'] = 'rejected' if not safe else 'requires_further_testing'
            report['heldout_improvement_over_baseline_and_heuristic'] = safe and better
            # Conservative confidence gate: small no-regression samples cannot establish equivalence.
            from .grade import wilson_interval
            regressions = len({tid for c in report['heldout_comparisons'] for tid in c['lost_tasks']})
            upper = wilson_interval(regressions, len(heldout))[1]
            report['heldout_regression_rate_ci95'] = wilson_interval(regressions, len(heldout))
            if safe and better and upper <= max_accuracy_drop and report['measurement_kind'] == 'external_provider':
                report['deployment'] = 'recommended'
        for entry in report['experiments']:
            reference = baseline if entry['partition'] == 'development' else hb
            entry['comparisons_to_original'] = [compare_variants(a, b) for a, b in zip(reference, entry['runs'])]
            entry['quality_constraints_satisfied'] = all(acceptable(a, b) for a, b in zip(reference, entry['runs']))
        report['recommended']['deployment'] = report['deployment']
        if report['deployment'] == 'rejected':
            report['recommended']['decision'] = 'reject'
        report['category_changes'] = {}
        for before, after in zip(baseline[0]['tasks'], chosen[0]['tasks']):
            category = before['category']
            report['category_changes'][category] = report['category_changes'].get(category, 0) + int(after['correct']) - int(before['correct'])
        report['api_calls'] = budget.calls
        report['observed_model_cost_usd'] = budget.cost if budget.cost_known else None
        return report
    except Exception as exc:
        report['status'] = 'incomplete'
        report['invalid_experiments'].append({'error_type': type(exc).__name__, 'reason': 'Evaluation failed; no deployment recommendation'})
        report['api_calls'] = budget.calls
        # Persist partial evidence without logging endpoint error bodies or credentials.
        from . import db
        rid = db.begin(cfg, 'optimization_validation', [])
        db.finish(cfg, rid, report, 'Validation incomplete: ' + type(exc).__name__)
        raise
