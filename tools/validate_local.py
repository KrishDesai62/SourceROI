"""Repeatable synthetic integration proof. No network, credentials, or real LLM claims."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.validation import optimize


def local_adapter(question, context, cfg):
    valid = [c for c in context if 'Revenue: 42' in c['text']]
    # Deliberately simulated usage; never represents a real tokenizer or provider.
    inputs, outputs = 75 + 25*len(context), 10
    return {'answer': '42' if valid else 'INSUFFICIENT_EVIDENCE',
            'citations': [c['id'] for c in valid], 'invalid_citations': [],
            'json_format_valid': True, 'input_tokens': inputs, 'output_tokens': outputs,
            'model_cost_usd': (inputs*2 + outputs*4)/1_000_000, 'data_cost_usd': 0.0,
            'model_latency_ms': 0.0, 'model_name': 'local-test-adapter',
            'cost_type': 'simulated', 'usage_source': 'local_simulated'}


def make_project(root):
    for sid, text in [('truth', 'Revenue: 42'), ('noise', 'Revenue outlook unavailable')]:
        folder = root/'sources'/sid
        folder.mkdir(parents=True)
        (folder/'data.md').write_text(text)
    tasks = [{'id': f'{split}-{i}', 'question': 'What is revenue?', 'expected': '42',
              'split': split} for split in ('development', 'heldout') for i in range(2)]
    (root/'benchmark.jsonl').write_text('\n'.join(json.dumps(t) for t in tasks))
    project = {'id': 'synthetic-validation', 'name': 'Synthetic validation',
               'measurement_kind': 'local_test_adapter', 'runner': 'rag_chat',
               'benchmark': 'benchmark.jsonl',
               'model': {'name': 'local-test-adapter', 'base_url': 'http://localhost:1/v1',
                         'input_price_per_million_usd': 2, 'output_price_per_million_usd': 4},
               'settings': {'max_chunks': 2, 'max_model_calls_per_run': 100,
                            'max_estimated_model_cost_usd': .02},
               'sources': [{'id': sid, 'name': sid, 'path': f'sources/{sid}',
                            'per_call_price_usd': price} for sid, price in [('truth', .03), ('noise', .01)]]}
    (root/'project.json').write_text(json.dumps(project))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        make_project(root)
        with patch('sourceroi.live.engine.run_chat', local_adapter):
            report = optimize(read_config(root), quality_floor=1, repeats=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(f'Synthetic report: {args.output}; deployment={report["deployment"]}')


if __name__ == '__main__':
    main()
