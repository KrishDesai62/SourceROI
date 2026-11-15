"""Run the frozen local-model comparison. Never downloads or calls remote models."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import load_benchmark, scan_sources
from sourceroi.live.datasets import verify_public_snapshot
from sourceroi.live.study import run_study, export_study
from local_llm import MODEL, RUNTIME, checksum


def run(project, output, root, *, accuracy_floor=0.0):
    cfg = read_config(project)
    model = cfg['model']
    if not model.get('local_only') or model.get('runtime') != 'llama_cpp' or model.get('base_url') != 'http://127.0.0.1:8788/v1':
        raise ValueError('Validation requires the approved, loopback-only pinned llama.cpp setup')
    manifest = json.loads((Path(root)/'manifest.json').read_text())
    if manifest['model'] != MODEL or manifest['runtime'] != RUNTIME:
        raise ValueError('Installed model/runtime manifest differs from the approved plan')
    if checksum(manifest['model_file']) != MODEL['sha256']:
        raise ValueError('Model checksum mismatch')
    # No commercial API prices or credential environment variables are configured/used.
    if any(model.get(k) is not None for k in ('input_price_per_million_usd', 'output_price_per_million_usd')):
        raise ValueError('Local validation must not simulate commercial API pricing')
    tasks = load_benchmark(cfg)
    verify_public_snapshot(cfg, scan_sources(cfg)[0])
    plan = {'model': MODEL, 'runtime': RUNTIME, 'project': str(Path(project).resolve()),
            'task_count': len(tasks), 'external_spend_usd': 0,
            'electricity_and_hardware_cost_usd': None, 'accuracy_floor': accuracy_floor,
            'quality_rule': 'No newly failed tasks against original, plus explicit absolute floor. Zero floor is a diagnostic relative-preservation experiment, not deployment-quality approval.',
            'groundedness_review': 'pending', 'heldout_passes_per_frozen_policy': 1,
            'benchmark_sha256': hashlib.sha256((Path(project)/cfg['benchmark']).read_bytes()).hexdigest()}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix('.plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    def progress(event):
        print(json.dumps(event), flush=True)
    report = run_study(cfg, objective='token_budget', quality_floor=accuracy_floor,
                       repeats=1, min_groundedness=None, notify=progress)
    report['local_validation'] = plan
    report['limitations'].append('Exact match can reject a factually acceptable paraphrase; published gold alternatives are retained unchanged. Claim-level human review is pending.')
    from sourceroi.live import db
    db.finish(cfg, report['run_id'], report)
    export_study(report, output)
    print(json.dumps({'output': str(output), 'status': report['status'],
                      'verdict': report['recommendation']['deployment_verdict'],
                      'external_spend_usd': 0}), flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, default=Path('workspace/local-llm-96'))
    p.add_argument('--output', type=Path, default=Path('docs/artifacts/local-llm-96.json'))
    p.add_argument('--root', type=Path, default=Path('workspace/.local-llm'))
    p.add_argument('--accuracy-floor', type=float, default=0.0)
    args = p.parse_args()
    run(args.project, args.output, args.root, accuracy_floor=args.accuracy_floor)
