"""Reproducible paired bootstrap over task groups, never over repeat replicas."""
import math
import random
import statistics


def objective_interval(baseline, candidate, tasks, objective, draws=1000):
    groups = {}
    for task in tasks:
        groups.setdefault(task.get('group_id', task['id']), []).append(task['id'])
    if len(groups) < 2:
        return None
    def by_id(entry):
        result = {}
        for run in entry['runs']:
            for row in run['tasks']:
                result.setdefault(row['id'], []).append(row)
        return result
    a, b = by_id(baseline), by_id(candidate)
    def value(source, ids):
        rows = [row for tid in ids for row in source[tid]]
        if objective == 'token_budget':
            if any(r['prompt_tokens'] is None or r['completion_tokens'] is None for r in rows):
                return None
            return sum(r['prompt_tokens']+r['completion_tokens'] for r in rows)/len(source[next(iter(source))])
        if objective == 'p95_latency':
            return sorted(r['end_to_end_latency_ms'] for r in rows)[math.ceil(.95*len(rows))-1]
        cost = None if any(r['model_cost_usd'] is None or r['data_cost_usd'] is None for r in rows) else sum(r['model_cost_usd']+r['data_cost_usd'] for r in rows)
        passed = sum(r['correct'] for r in rows)
        latency = statistics.mean(r['end_to_end_latency_ms'] for r in rows)
        if objective == 'latency':
            return latency
        if cost is None or not passed:
            return None
        cps = cost/passed
        if objective == 'cost_per_success':
            return cps
        return cps*1000 + latency + (1-passed/len(rows))*10000
    generator = random.Random(1729)
    names = sorted(groups)
    deltas = []
    for _ in range(draws):
        ids = [tid for _ in names for tid in groups[generator.choice(names)]]
        av, bv = value(a, ids), value(b, ids)
        if av is None or bv is None or not math.isfinite(av) or not math.isfinite(bv):
            return None
        deltas.append(bv-av)
    deltas.sort()
    return [round(deltas[int(.025*(draws-1))], 8), round(deltas[int(.975*(draws-1))], 8)]
