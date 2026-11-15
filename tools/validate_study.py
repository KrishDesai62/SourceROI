"""Standalone synthetic mechanics check. No APIs, downloads, or real-model claims."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.study import run_study, export_study


def create_project(root):
    tasks = []
    for sid in ('reports', 'cash', 'commentary'):
        (root/'sources'/sid).mkdir(parents=True)
    for index, company in enumerate(('Aster', 'Boreal', 'Cirrus', 'Doria'), 1):
        revenue, cash = str(index*100), str(index*10)
        (root/'sources/reports'/f'{company}.txt').write_text(f'{company} revenue: {revenue}. Reported annual revenue for {company}.')
        (root/'sources/cash'/f'{company}.txt').write_text(f'{company} cash: {cash}. Reported available cash for {company}.')
        (root/'sources/commentary'/f'{company}.txt').write_text(f'{company} revenue and cash discussion. Figures are unavailable in this commentary.')
        split = 'development' if index <= 2 else 'heldout'
        tasks.extend([{'id': company+'-lookup', 'question': f'What is {company} revenue?', 'expected': revenue,
                       'split': split, 'group_id': company, 'review_status': 'synthetic'},
                      {'id': company+'-comparison', 'question': f'Compare {company} revenue and cash.', 'expected': revenue+' and '+cash,
                       'split': split, 'group_id': company, 'review_status': 'synthetic'}])
    (root/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks)+'\n')
    cfg = {'id': 'standalone-synthetic-study', 'name': 'Standalone synthetic study',
           'measurement_kind': 'local_test_adapter', 'runner': 'rag_chat', 'benchmark': 'benchmark.jsonl',
           'model': {'name': 'simulated-extractor', 'base_url': 'http://localhost:1/v1',
                     'input_price_per_million_usd': 2, 'output_price_per_million_usd': 4},
           'settings': {'max_chunks': 4, 'chunk_chars': 500, 'overlap_chars': 0,
                        'max_model_calls_per_run': 1000, 'max_estimated_model_cost_usd': .25},
           'sources': [{'id': sid, 'name': sid, 'path': 'sources/'+sid, 'per_call_price_usd': 0}
                       for sid in ('reports', 'cash', 'commentary')]}
    (root/'project.json').write_text(json.dumps(cfg))


def simulated_model(question, context, cfg):
    issuer = re.search(r'\b(Aster|Boreal|Cirrus|Doria)\b', question).group()
    facts, cites = {}, []
    for c in context:
        for field, value in re.findall(r'\b'+issuer+r' (revenue|cash): (\d+)\b', c['text']):
            facts[field] = value
            cites.append(c['id'])
    required = ['revenue', 'cash'] if question.startswith('Compare') else ['revenue']
    answer = ' and '.join(facts[f] for f in required) if all(f in facts for f in required) else 'INSUFFICIENT_EVIDENCE'
    input_tokens = 50 + sum((len(c['text'])+3)//4 for c in context)
    output_tokens = max(1, len(answer.split()))
    return {'answer': answer, 'citations': list(dict.fromkeys(cites)), 'invalid_citations': [],
            'json_format_valid': True, 'input_tokens': input_tokens, 'output_tokens': output_tokens,
            'model_cost_usd': (input_tokens*2+output_tokens*4)/1_000_000, 'data_cost_usd': 0,
            'model_latency_ms': 0, 'model_name': 'simulated-extractor', 'cost_type': 'simulated',
            'usage_source': 'local_simulated'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        create_project(root)
        with patch('sourceroi.live.engine.run_chat', simulated_model):
            report = run_study(read_config(root), repeats=2, quality_floor=1, min_groundedness=None)
        export_study(report, args.output)
    print(json.dumps({'report': str(args.output), 'api_calls': report['api_calls'],
                      'verdict': report['observed_verdict'], 'deployment': report['deployment']}))


if __name__ == '__main__':
    main()
