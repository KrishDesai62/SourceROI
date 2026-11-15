"""Retrieval-only checks on published evidence. Never produces model-quality scores."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics

from .config import secure_path
from .ingest import load_benchmark, scan_sources
from .policies import select_context
from .study import policies
from .validation import split_tasks


def audit_retrieval(cfg):
    tasks = load_benchmark(cfg)
    dev, heldout = split_tasks(tasks)
    if not heldout or any(not t['evidence'] for t in tasks):
        raise ValueError('Public audit requires grouped partitions and published evidence for every task')
    docs, chunks = scan_sources(cfg)
    from .datasets import verify_public_snapshot
    verify_public_snapshot(cfg, docs)
    root = Path(cfg['_root'])
    for task in tasks:
        for reference in task['evidence']:
            doc = next((d for d in docs if d['id'] == reference['document_id']), None)
            if doc is None:
                raise ValueError('Published evidence references missing document')
            from .ingest import extract_document
            text = extract_document(secure_path(root, doc['path']),cfg)
            if reference['quote'] not in text:
                raise ValueError('Published evidence quote does not match document')
    def evaluate(selected, policy):
        local = deepcopy(cfg)
        local['settings']['retrieval_policy'] = policy
        rows = []
        for task in selected:
            context, decision = select_context(task['question'], chunks, local)
            evidence = task['evidence']
            found = [e for e in evidence if any(c['document_id'] == e['document_id'] and e['quote'] in c['text'] for c in context)]
            expected_docs = {e['document_id'] for e in evidence}
            actual_docs = {c['document_id'] for c in context}
            rows.append({'id': task['id'], 'dataset': task['dataset'], 'selected_chunks': decision['selected_ids'],
                         'context_characters': sum(len(c['text']) for c in context),
                         'support_quote_coverage': len(found)/len(evidence),
                         'support_document_coverage': len(expected_docs & actual_docs)/len(expected_docs),
                         'all_support_quotes_present': len(found) == len(evidence)})
        return {'tasks': rows, 'all_support_tasks': sum(r['all_support_quotes_present'] for r in rows),
                'task_count': len(rows), 'mean_quote_coverage': statistics.mean(r['support_quote_coverage'] for r in rows),
                'context_characters': sum(r['context_characters'] for r in rows)}
    development = [(family, policy, evaluate(dev, policy)) for family, policy in policies(cfg)]
    families = sorted({family for family, _, _ in development} - {'coverage'})
    frozen = {}
    for family in families:
        entries = [(policy, result) for f, policy, result in development if f == family]
        policy, _ = min(entries, key=lambda entry: (-entry[1]['all_support_tasks'], -entry[1]['mean_quote_coverage'], entry[1]['context_characters'], json.dumps(entry[0], sort_keys=True)))
        frozen[family] = policy
    # This chooses on retrieval evidence, NOT on model outcomes. Do not call it a model optimizer result.
    from .policies import task_kind
    mapping = {}
    for kind in sorted({task_kind(t['question']) for t in dev}):
        ids = {t['id'] for t in dev if task_kind(t['question']) == kind}
        def key(entry):
            rows = [r for r in entry[2]['tasks'] if r['id'] in ids]
            return (-sum(r['all_support_quotes_present'] for r in rows),
                    -sum(r['support_quote_coverage'] for r in rows),
                    sum(r['context_characters'] for r in rows), json.dumps(entry[1], sort_keys=True))
        mapping[kind] = min(development, key=key)[1]
    frozen['sourceroi_retrieval_proxy'] = {'name': 'learned', 'by_kind': mapping}
    results = {name: {**evaluate(heldout, policy), 'frozen_policy': policy} for name, policy in frozen.items()}
    provenance = secure_path(root, cfg.get('data_provenance', 'provenance.json'))
    return {'kind': 'real_document_retrieval_only', 'model_calls': 0, 'input_tokens': None, 'output_tokens': None,
            'model_cost_usd': None, 'answer_accuracy': None, 'groundedness': None,
            'provenance_sha256': hashlib.sha256(provenance.read_bytes()).hexdigest(),
            'benchmark_sha256': hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest(),
            'manifest': {d['id']: d['fingerprint'] for d in docs},
            'partitions': {'development': [t['id'] for t in dev], 'heldout': [t['id'] for t in heldout]},
            'comparisons': results,
            'limitations': ['Only retrieval coverage and character counts are measured; no answer model was run.',
                           'The proxy policy is fit to development evidence coverage, not measured model quality or tokens.',
                           'Complete reference quote inclusion is a strict retrieval diagnostic, not semantic groundedness.',
                           'Chunking can split long support sentences; absent whole quotes do not prove all useful evidence absent.',
                           'No superiority or deployment recommendation follows from this retrieval-only audit.']}
